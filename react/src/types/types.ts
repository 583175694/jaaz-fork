import { OrderedExcalidrawElement } from '@excalidraw/excalidraw/element/types'
import { AppState, BinaryFiles } from '@excalidraw/excalidraw/types'

export type ToolCallFunctionName =
  | 'generate_image'
  | 'generate_storyboard_from_main_image'
  | 'generate_multiview_variant'
  | 'generate_video_from_storyboard'
  | 'generate_video_by_veo3_apipod'
  | 'prompt_user_multi_choice'
  | 'prompt_user_single_choice'
  | 'write_plan'
  | 'finish'

export type ToolCall = {
  id: string
  type: 'function'
  function: {
    name: ToolCallFunctionName
    arguments: string
  }
  result?: string // Only for manually merged message list by mergeToolCallResult
}
export type MessageContentType = MessageContent[] | string
export type MessageContent =
  | { text: string; type: 'text' }
  | { image_url: { url: string }; type: 'image_url' }

export type ToolResultMessage = {
  role: 'tool'
  tool_call_id: string
  content: string
}
export type AssistantMessage = {
  role: 'assistant'
  tool_calls?: ToolCall[]
  content?: MessageContent[] | string
}
export type UserMessage = {
  role: 'user'
  content: MessageContent[] | string
}
export type Message = UserMessage | AssistantMessage | ToolResultMessage

export type PendingType = 'text' | 'image' | 'tool' | false

export interface ChatSession {
  id: string
  model: string
  provider: string
  title: string | null
  created_at: string
  updated_at: string
}
export interface MessageGroup {
  id: number
  role: string
  messages: Message[]
}

export enum EAgentState {
  IDLE = 'IDLE',
  RUNNING = 'RUNNING',
  FINISHED = 'FINISHED',
  ERROR = 'ERROR',
}

export type LLMConfig = {
  models: Record<
    string,
    {
      type?: 'text' | 'image' | 'video'
      is_custom?: boolean
      is_disabled?: boolean
    }
  >
  url: string
  api_key: string
  max_tokens?: number
  is_custom?: boolean
}

export interface AppStateWithVideos extends AppState {
  videoElements?: any[]
}

export type CanvasData = {
  elements: Readonly<OrderedExcalidrawElement[]>
  appState: AppStateWithVideos
  files: BinaryFiles
  production?: CanvasProductionState
}

export type CameraTarget = {
  azimuth: number
  elevation: number
  framing: 'close' | 'medium' | 'full' | 'wide'
  preset_name: string
}

export type CameraState = {
  preset_name: string
  view_type: string
  azimuth: number
  elevation: number
  framing: 'close' | 'medium' | 'full' | 'wide'
}

export type ShotSchemaV2 = {
  shot_id: string
  order_index: number
  narrative_role: string
  shot_goal_zh: string
  shot_goal_en: string
  framing: 'close' | 'medium' | 'full' | 'wide'
  gaze_target: string
  subject_state: string
  background_visibility: string
  information_gain: string
  must_change_vs_prev: string[]
  inherits_from: string
  locked_constraints: string[]
  allowed_variations: string[]
  camera_target: CameraTarget
}

export type StoryboardImageMeta = {
  storyboard_id: string
  shot_id: string
  shot_family_id?: string
  variant_id: string
  source_main_image_file_id?: string
  continuity_id?: string
  continuity_version?: number
  source_variant_id?: string
  generation_mode?: string
  generation_pass?: string
  narrative_role?: string
  shot_goal?: string
  view_type?: string
  azimuth?: number
  elevation?: number
  framing?: 'close' | 'medium' | 'full' | 'wide'
  gaze_target?: string
  subject_state?: string
  background_visibility?: string
  information_gain?: string
  must_change_vs_prev?: string[]
  camera_target?: CameraTarget
  camera_state?: CameraState
  is_primary_variant?: boolean
  variant_count?: number
  primary_variant_count?: number
  shot_evaluation?: {
    accepted?: boolean
    reasons?: string[]
    score?: number
  }
  prompt_snapshot?: string
  summary?: string
}

export type ContinuityAsset = {
  continuity_id: string
  version: number
  status: 'draft' | 'confirmed' | 'superseded'
  source_main_image_file_id: string
  prompt: string
  scene_bible?: Record<string, unknown>
  character_bible?: Record<string, unknown>
  camera_baseline?: Record<string, unknown>
  locked_rules?: Record<string, unknown>
  allowed_variations?: Record<string, unknown>
  continuity_summary?: Record<string, unknown>
  main_image_summary?: Record<string, unknown>
  created_at?: number
  updated_at?: number
}

export type StoryboardPlanAsset = {
  storyboard_id: string
  continuity_id: string
  continuity_version?: number
  source_main_image_file_id?: string
  aspect_ratio: string
  mode?: string
  shot_count: number
  variant_count_per_shot: number
  prompt?: string
  shots?: ShotSchemaV2[]
  status?: 'draft' | 'confirmed'
  created_at?: number
  updated_at?: number
}

export type VideoBriefAsset = {
  brief_id: string
  storyboard_id: string
  continuity_id: string
  continuity_version?: number
  duration: number
  aspect_ratio: string
  resolution: string
  prompt?: string
  display_summary?: Record<string, unknown>
  status?: 'draft' | 'confirmed'
  created_at?: number
  updated_at?: number
}

export type CanvasProductionState = {
  current_continuity_id?: string
  continuity_assets?: Record<string, ContinuityAsset>
  storyboard_plans?: Record<string, StoryboardPlanAsset>
  video_briefs?: Record<string, VideoBriefAsset>
}

export type Session = {
  created_at: string
  id: string
  model: string
  provider: string
  title: string
  updated_at: string
}

export type Model = {
  provider: string
  model: string
  url: string
}
