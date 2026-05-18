# Client Media Queue V1 Plan

## Background

The project currently has no durable user concept. Most runtime isolation is
based on `session_id`, while parts of media generation use ad hoc in-memory
guards:

- normal chat streams are tracked by `session_id`
- direct video uses `generation_jobs`
- storyboard / multiview / refine reject follow-up requests when the same
  `session_id` is already busy

This is not enough for the desired UX:

- a browser should get a stable lightweight identity
- all generated content should be associated with that identity
- media tasks should queue by user instead of being rejected
- the UI should show a lightweight preview of the current and upcoming tasks

This document captures the first practical implementation plan. It aims to fix
the product problem with the smallest reasonable architecture step, while
avoiding an oversized rewrite.

## Goal

Introduce a lightweight `clientId` and a client-scoped media task queue so that:

1. a new browser instance generates a stable `clientId` and persists it in
   `localStorage`
2. new canvases, sessions, and media generation jobs are associated with that
   `clientId`
3. media generation runs as a FIFO queue per `clientId`
4. while one media task is running, later media tasks are accepted and queued
   instead of being rejected
5. the input area shows a lightweight queue preview above the textarea

## Non-goals

This V1 intentionally does not attempt to solve everything.

- It does not introduce a real account system.
- It does not make `clientId` a secure identity boundary.
- It does not merge normal `/api/chat` traffic into the same queue.
- It does not require a full websocket room refactor in the first step.
- It does not try to backfill old data into perfect `clientId` ownership.

## Why This Scope

The key product pain is in media workflows, not generic chat. A user currently
expects a second image or video generation request to "line up", but the system
either blocks it in the frontend or rejects it in the backend.

Keeping V1 focused on media tasks gives us:

- a clear user-visible improvement
- a consistent queue model for the workflows that need it most
- limited blast radius compared with rewriting all session and chat behavior

## Current State Summary

### Identity

There is no durable browser-scoped identity today. New canvas and session IDs
are generated ad hoc on the frontend.

### Execution model

- `direct_video` already persists jobs in `generation_jobs`
- `direct_storyboard`, `direct_multiview`, and `storyboard_refine` do not use a
  common persisted queue
- several entry points block follow-up work instead of queuing it

### Frontend UX

- media generators use local in-flight guards
- chat textarea uses a broad `pending` state that blocks repeat submissions
- there is no dedicated queue UI above the input

## V1 Design Principles

1. Use `clientId` as a lightweight runtime partition, not as a full user model.
2. Queue only media generation in V1.
3. Prefer persisted queue state over pure in-memory state.
4. Accept requests quickly and execute them in background workers.
5. Keep the queue UI lightweight and easy to read.
6. Preserve room for a later V2 with stronger isolation and more parallelism.

## V1 Decision Checklist

The following boundaries are explicitly locked for V1 and should be treated as
implementation constraints rather than open questions.

1. Legacy data is not shown. `clientId` only applies to new data created after
   this feature lands.
2. Queue UI only shows tasks related to the current canvas.
3. Only direct media entry points are queued in V1:
   `direct_storyboard`, `direct_multiview`, `storyboard_refine`, and
   `direct_video`.
4. There is no draft job state. If a flow requires confirmation, the real job
   is created only after confirmation succeeds.
5. Deduplication uses lightweight frontend submit debouncing plus conservative
   backend deduplication for `queued` and `running` jobs with the same
   normalized payload under the same `client_id`.
6. Normal `/api/chat` remains outside the media queue and stays available while
   media tasks are queued or running.
7. Chat-triggered media generation through the generic agent/tool path is out
   of scope for V1 and is not automatically routed through the client media
   queue.

## Scope of Media Tasks

The following task types enter the client queue in V1:

- `direct_storyboard`
- `direct_multiview`
- `storyboard_refine`
- `direct_video`

Normal `/api/chat` remains outside this queue.

Important boundary:

- V1 only queues direct media entry points listed above
- generic chat-driven tool execution is not normalized into this queue in V1

## Client Identity

### Frontend behavior

Add a small client identity helper, for example:

- `react/src/lib/client.ts`

Suggested API:

```ts
export function getOrCreateClientId(): string
export function getClientId(): string
```

Behavior:

- on first app load, generate `cli_<random>`
- persist it in `localStorage`
- reuse the same value across refreshes

Suggested storage key:

- `jaaz_client_id`

### Important boundary

`clientId` is a lightweight browser/device identity only.

- clearing local storage creates a new identity
- another browser creates another identity
- another machine creates another identity

This is acceptable for V1 because the goal is queue ownership and local
isolation, not cross-device accounts.

## Data Model Changes

Add a new migration, suggested name:

- `v5_add_client_identity_and_media_queue.py`

### New columns

Add `client_id` to:

- `canvases`
- `chat_sessions`
- `generation_jobs`

Add `summary_text` to:

- `generation_jobs`

### Suggested meaning

- `client_id`: who owns the canvas/session/job
- `summary_text`: short display string for queue preview UI

### Suggested indexes

For `generation_jobs`:

- `(client_id, status, created_at DESC)`
- `(client_id, created_at ASC)`
- `(client_id, canvas_id, created_at DESC)`

For `chat_sessions` and `canvases`, add indexes that support listing by
`client_id` and recent update time.

### Legacy data handling

Do not force a risky backfill in V1.

Locked V1 behavior:

- new rows must always write `client_id`
- old rows may remain `NULL`
- new UI paths only show rows owned by the current `client_id`
- legacy rows without `client_id` are not shown in V1

Rationale:

- avoids ambiguous ownership rules
- avoids fragile backfill heuristics
- keeps queue and listing behavior deterministic for new data

## Queue Model

### Queue dimension

Queue by `client_id`.

### Execution rule

At most one media task runs at a time for a given `client_id`.

### Ordering rule

Use FIFO:

- oldest `queued` job runs next
- order by `created_at ASC`, tie-break by `id ASC`

### Status lifecycle

Use:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

### Why single-flight per client in V1

This is intentionally conservative.

Benefits:

- easy to explain to users
- predictable ordering
- simpler recovery logic
- smaller implementation risk

Tradeoff:

- different media types cannot run in parallel for the same client

This is acceptable in V1. We may later evolve to resource-aware concurrency if
the product needs it.

## Job Model

Reuse `generation_jobs` as the single persisted queue for media work.

### Supported job types in V1

- `direct_storyboard`
- `direct_multiview`
- `storyboard_refine`
- `direct_video`

### Required persisted fields

Each media job should store:

- `id`
- `client_id`
- `session_id`
- `canvas_id`
- `type`
- `status`
- `provider`
- `request_payload`
- `summary_text`
- `progress`
- `error_message`
- timestamps

### Summary text examples

- `视频 6s / 16:9`
- `分镜 4 张 / 16:9`
- `多视角候选 45° / medium`
- `编辑当前镜头 / append`

This should be generated on the backend when creating the job so the frontend
does not need to parse heterogeneous payloads.

## Backend API Changes

## Request payloads

Add `client_id` to:

- `POST /api/canvas/create`
- `POST /api/chat`
- `POST /api/direct_storyboard`
- `POST /api/direct_multiview`
- `POST /api/storyboard/refine`
- `POST /api/direct_video`

### Query filtering

Update data access so new paths filter by `client_id`:

- list canvases
- get canvas
- list sessions
- list generation jobs

## Queue APIs

Add a client queue listing API.

Suggested endpoint:

- `GET /api/jobs`

Suggested query params:

- `scope=client`
- `canvas_id=<optional>`
- `status=queued,running`
- `limit=20`

Suggested response:

```json
{
  "jobs": [
    {
      "id": "job_xxx",
      "client_id": "cli_xxx",
      "session_id": "ses_xxx",
      "canvas_id": "can_xxx",
      "type": "direct_video",
      "status": "running",
      "summary_text": "视频 6s / 16:9",
      "progress": 35,
      "created_at": "2026-05-18T00:00:00Z",
      "started_at": "2026-05-18T00:00:02Z"
    }
  ]
}
```

## Execution Model Refactor

### V1 direction

Change media endpoints from "run immediately and block until done" to
"persist job, accept request, execute in background worker".

### New behavior

For each media submission:

1. validate request
2. create a persisted media job with status `queued`
3. emit `job_queued`
4. ensure a worker exists for that `client_id`
5. return `{ status: "accepted", job_id, job }`

### Worker model

Maintain an in-memory worker registry keyed by `client_id`, for example:

- `client_worker_tasks: dict[str, asyncio.Task[Any]]`

Worker loop:

1. select the next queued job for the client
2. mark it `running`
3. execute the corresponding runner
4. mark it finished
5. continue until no queued jobs remain
6. exit and remove the worker entry

### Recovery

On server restart:

- recover `queued` jobs
- recover `running` jobs conservatively

Suggested V1 rule:

- jobs already `queued` can be resumed
- jobs marked `running` at startup may be reset to `queued` unless a provider
  contract requires different handling

## Media Runner Changes

### `direct_video`

This path already uses `generation_jobs`, so it should be adapted into the new
client-scoped worker model instead of the current global-only flow.

### `direct_storyboard`

Current behavior is effectively synchronous from the API point of view. V1
should convert it to:

- create job
- return accepted
- execute storyboard generation in the queue worker

### `direct_multiview`

Same treatment as storyboard:

- create job
- return accepted
- execute via queue worker

### `storyboard_refine`

Same treatment:

- create job
- return accepted
- execute via queue worker

## Prompt Confirmation Handling

V1 should only queue executable media work.

That means prompt confirmation should happen before a job is queued.

Recommended rule:

- if a flow requires user confirmation, complete the confirmation first
- only create the media job after confirmation succeeds
- do not create a draft or placeholder job before confirmation

Reason:

- avoids a queue being blocked by a not-yet-confirmed task
- keeps queue semantics clean and predictable
- makes queue UI easier to explain

## Frontend Changes

## Request plumbing

All relevant API calls should include `client_id`, sourced from
`getOrCreateClientId()`.

### Recommended implementation

- centralize this in API helper functions rather than repeating it inside each
  component
- if possible, also pass `client_id` in websocket auth payload for future use

## Queue state

Introduce dedicated queue state for media tasks instead of overloading the
existing generic `pending` flag.

Suggested frontend state split:

- `chatPending`
- `mediaQueueItems`
- `isSubmittingMedia`

Locked V1 behavior:

- `chatPending` and media queue state are independent
- a running media task must not block normal `/api/chat` submissions
- a finished chat response must not be treated as "the whole page is idle" if
  media queue work still exists

### Why split state

Current `pending` serves too many purposes:

- chat stream running
- tool call running
- image/video generation ongoing

That makes it hard to support a visible queue without accidentally blocking
valid submissions.

## Queue UI

Add a lightweight component above the chat textarea, for example:

- `QueuePreview`

Display:

- one current running task if present
- up to three queued tasks after it

Suggested copy examples:

- `正在生成：视频 6s / 16:9`
- `接下来：分镜 4 张 / 16:9`
- `接下来：多视角候选 45° / medium`

### Display strategy

Backend scheduling is by `client_id`, but UI should prioritize clarity:

- only show queue items related to the current canvas in V1
- do not show cross-canvas queue items in the queue preview

Rationale:

- keeps the first queue UI easy to understand
- matches the current page context
- avoids introducing a cross-canvas queue mental model in V1

## Frontend submission behavior

Remove "hard reject because something is already running" behavior for media
submissions.

Replace it with:

- allow submission while another media task is running
- prevent accidental duplicate double-click submission for the same button
- rely on backend queueing for execution ordering
- keep conservative backend deduplication for equivalent active jobs

### Important distinction

We are not removing all protection.

We are changing from:

- "if any media task exists, reject immediately"

to:

- "allow queueing, keep lightweight submit-time debouncing, and apply backend
  deduplication for equivalent active jobs"

### Deduplication rule

Locked V1 behavior:

- frontend prevents accidental rapid repeat submission from the same interaction
- backend deduplicates only against `queued` and `running` jobs
- backend deduplication key is:
  `client_id + job_type + normalized request payload`
- completed jobs do not block a user from intentionally submitting the same
  request again later

## WebSocket Strategy

V1 should extend existing queue-related websocket payloads with `client_id`.

Suggested events:

- `job_queued`
- `job_running`
- `job_progress`
- `job_succeeded`
- `job_failed`

### Delivery strategy in V1

Do not block the feature on a full socket room refactor.

V1 may continue using broadcast delivery if necessary, provided:

- queue events include `client_id`
- frontend filters by `client_id`
- queue UI only updates for the active client

### V2 direction

Later, move to:

- `client:<client_id>` socket rooms

This will reduce noise and improve correctness, but it is not required to prove
the queue UX in V1.

## DB and Service Layer Tasks

Recommended implementation checklist:

1. Add migration for `client_id` and `summary_text`.
2. Update DB service create/list/get methods to accept `client_id`.
3. Update canvas/session creation paths to persist `client_id`.
4. Generalize media job creation beyond direct video.
5. Add client worker orchestration.
6. Convert storyboard, multiview, and refine routes to accepted background jobs.
7. Add client queue listing API.
8. Emit queue websocket updates with `client_id`.

## Frontend Tasks

Recommended implementation checklist:

1. Add `clientId` helper and initialize it on app boot.
2. Include `client_id` in canvas/session/media requests.
3. Add queue fetching API wrapper.
4. Add websocket queue update handling filtered by `client_id`.
5. Add `QueuePreview` above the textarea.
6. Split queue state from generic chat pending state.
7. Remove media hard-block guards and replace them with lightweight submit
   debouncing.

## Acceptance Criteria

V1 is considered successful when all of the following are true:

1. a browser gets a stable `clientId` on first load and keeps it after refresh
2. new canvases, sessions, and media jobs persist `client_id`
3. while one media task is running, submitting another media task returns
   `accepted` instead of rejecting with "please wait"
4. media tasks execute FIFO per `client_id`
5. the input area shows a lightweight preview of the running task and queued
   tasks
6. two different browser identities do not share the same media queue
7. normal `/api/chat` behavior continues to work as before

## Risks and Tradeoffs

### Risk: over-scoping V1

If we try to solve full user accounts, full websocket isolation, and complete
history migration at the same time, delivery risk increases sharply.

Mitigation:

- keep V1 centered on client-scoped media queueing

### Risk: duplicate tasks

Allowing queueing makes accidental repeat submissions more likely.

Mitigation:

- keep submit-time debouncing
- add backend deduplication on normalized payloads for active jobs only

### Risk: legacy data visibility

Old data without `client_id` may no longer appear in the same way.

Mitigation:

- explicitly hide legacy rows in V1
- treat this as a known product transition, not an implementation accident

### Risk: one queue per client may feel slow

Users may eventually want image and video tasks to overlap.

Mitigation:

- accept single-flight simplicity in V1
- keep architecture extensible for future resource-aware concurrency

## V2 Candidates

Possible follow-up improvements after V1 is stable:

- websocket room isolation by `client_id`
- richer queue display across canvases
- server-side queue cancellation and reordering
- parallelism by resource type instead of strict single-flight
- migration from `clientId` to a true account-backed user model
- optional inclusion of chat tasks in a broader orchestration layer
- optional normalization of chat-triggered media generation into the same queue

## Recommended File Targets

Likely implementation touch points:

- `react/src/lib/client.ts`
- `react/src/App.tsx`
- `react/src/api/canvas.ts`
- `react/src/api/video.ts`
- `react/src/api/storyboard.ts`
- `react/src/components/chat/Chat.tsx`
- `react/src/components/chat/ChatTextarea.tsx`
- `react/src/components/chat/ChatCanvasVideoGenerator.tsx`
- `react/src/components/chat/ChatCanvasStoryboardGenerator.tsx`
- `react/src/components/chat/ChatCanvasMultiviewGenerator.tsx`
- `server/services/db_service.py`
- `server/services/generation_job_service.py`
- `server/services/direct_video_service.py`
- `server/services/direct_storyboard_service.py`
- `server/routers/chat_router.py`
- `server/routers/canvas.py`
- `server/services/migrations/`

## Final Recommendation

Implement V1 as a focused client-scoped media queue, not as a full user-system
rewrite.

That keeps the solution aligned with the real product problem:

- tasks should belong to a stable browser identity
- repeated media submissions should queue instead of fail
- users should see what is running and what comes next

This delivers meaningful UX improvement without forcing the project into a much
heavier platform migration in one step.
