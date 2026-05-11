import asyncio
import json
from typing import Any, Dict, List, Optional, TypedDict

from nanoid import generate

from services.db_service import db_service
from services.prompt_confirmation_service import request_prompt_bundle_confirmation
from services.production_workflow_service import (
    build_continuity_asset,
    build_storyboard_plan_asset,
    get_current_continuity_asset,
    load_canvas_data,
    upsert_continuity_asset,
    upsert_storyboard_plan,
)
from services.stream_service import add_stream_task, get_stream_task, remove_stream_task
from services.websocket_service import send_to_websocket
from services.tool_service import tool_service
from tools.utils.image_generation_core import generate_image_with_provider


class MainImageAnchor(TypedDict, total=False):
    anchor_id: str
    source_file_id: str
    subject_type: str
    subject_summary: str
    environment_identity: Dict[str, Any]
    lighting_identity: Dict[str, Any]
    style_identity: Dict[str, Any]
    source_prompt_excerpt: str


class ContinuityBible(TypedDict, total=False):
    continuity_id: str
    anchor_id: str
    hard_constraints: Dict[str, Any]
    soft_constraints: Dict[str, Any]
    allowed_variations: List[str]


class StoryboardShot(TypedDict, total=False):
    shot_id: str
    order_index: int
    narrative_role: str
    shot_goal: str
    continuity_anchor: str
    default_view: str
    allowed_views: List[str]
    framing: str
    gaze_target: str
    subject_state: str
    background_visibility: str
    information_gain: str
    must_change_vs_prev: List[str]


class StoryboardPlan(TypedDict, total=False):
    storyboard_id: str
    source_main_image_file_id: str
    mode: str
    aspect_ratio: str
    shot_count: int
    variant_count_per_shot: int
    continuity_id: str
    shots: List[StoryboardShot]


class ShotEvaluationResult(TypedDict, total=False):
    accepted: bool
    reasons: List[str]
    score: int


def _build_shot_family_id(storyboard_id: str, shot_id: str) -> str:
    normalized_storyboard_id = str(storyboard_id or "sb").strip() or "sb"
    normalized_shot_id = str(shot_id or "S").strip() or "S"
    return f"{normalized_storyboard_id}:{normalized_shot_id}"


def _build_camera_state(
    *,
    preset_name: str,
    view_type: str,
    azimuth: int,
    elevation: int,
    framing: str,
) -> Dict[str, Any]:
    return {
        "preset_name": preset_name or view_type or "custom",
        "view_type": view_type or preset_name or "custom",
        "azimuth": int(azimuth),
        "elevation": int(elevation),
        "framing": str(framing or "medium"),
    }


REFERENCE_IMAGE_TOOL_MAPPING: Dict[str, Dict[str, str]] = {
    "generate_image_by_gpt_image_2_edit_apipod": {
        "provider": "apipodgptimage",
        "model": "gpt-image-2-edit",
    },
    "generate_image_by_flux_kontext_pro_jaaz": {
        "provider": "jaaz",
        "model": "black-forest-labs/flux-kontext-pro",
    },
    "generate_image_by_flux_kontext_max_jaaz": {
        "provider": "jaaz",
        "model": "black-forest-labs/flux-kontext-max",
    },
    "generate_image_by_flux_kontext_max": {
        "provider": "jaaz",
        "model": "black-forest-labs/flux-kontext-max",
    },
}


def _normalize_tool_id(data: Dict[str, Any]) -> str:
    return str(data.get("image_tool_id", "") or "").strip()


def _normalize_prompt(data: Dict[str, Any]) -> str:
    return str(data.get("prompt", "") or "").strip()


def _normalize_main_image_file_id(data: Dict[str, Any]) -> str:
    return str(data.get("main_image_file_id", "") or "").strip()


def _normalize_reference_image_file_id(data: Dict[str, Any], key: str) -> str:
    return str(data.get(key, "") or "").strip()


def _normalize_aspect_ratio(data: Dict[str, Any]) -> str:
    value = str(data.get("aspect_ratio", "16:9") or "16:9").strip()
    return value or "16:9"


def _normalize_shot_count(data: Dict[str, Any]) -> int:
    try:
        value = int(data.get("shot_count", 4) or 4)
    except (TypeError, ValueError):
        value = 4
    return min(max(value, 2), 8)


def _normalize_variant_count(data: Dict[str, Any]) -> int:
    try:
        value = int(data.get("variant_count_per_shot", 3) or 3)
    except (TypeError, ValueError):
        value = 3
    return min(max(value, 1), 4)


def _primary_variant_budget(_: int) -> int:
    return 1


def _normalize_preview_only(data: Dict[str, Any]) -> bool:
    return bool(data.get("preview_only", False))


def _normalize_replace_source(data: Dict[str, Any]) -> bool:
    return bool(data.get("replace_source", False))


def _normalize_mode(data: Dict[str, Any], default: str = "append") -> str:
    value = str(data.get("mode", default) or default).strip().lower()
    if value in {"append", "replace"}:
        return value
    return default


def _normalize_messages(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages = data.get("messages", [])
    return messages if isinstance(messages, list) else []


def _resolve_reference_tool(requested_tool_id: str) -> Dict[str, str]:
    registered_tools = tool_service.get_all_tools()
    if requested_tool_id in registered_tools and requested_tool_id in REFERENCE_IMAGE_TOOL_MAPPING:
        return {
            "tool_id": requested_tool_id,
            **REFERENCE_IMAGE_TOOL_MAPPING[requested_tool_id],
        }

    for tool_id in (
        "generate_image_by_gpt_image_2_edit_apipod",
        "generate_image_by_flux_kontext_pro_jaaz",
        "generate_image_by_flux_kontext_max_jaaz",
        "generate_image_by_flux_kontext_max",
    ):
        if tool_id in registered_tools and tool_id in REFERENCE_IMAGE_TOOL_MAPPING:
            return {
                "tool_id": tool_id,
                **REFERENCE_IMAGE_TOOL_MAPPING[tool_id],
            }

    raise RuntimeError(
        "No reference-image capable image tool is configured. Please enable GPT Image 2 Edit or Flux Kontext."
    )


async def _load_canvas_context(canvas_id: str) -> Dict[str, Any]:
    return await load_canvas_data(canvas_id)


def _get_canvas_file(canvas_data: Dict[str, Any], file_id: str) -> Dict[str, Any]:
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        return {}
    file_info = files.get(file_id)
    return file_info if isinstance(file_info, dict) else {}


def _get_canvas_image_element(canvas_data: Dict[str, Any], file_id: str) -> Dict[str, Any]:
    elements = canvas_data.get("elements", []) if isinstance(canvas_data, dict) else []
    if not isinstance(elements, list):
        return {}
    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get("type") == "image" and str(element.get("fileId", "") or "") == file_id:
            return element
    return {}


def _build_main_image_anchor(
    file_id: str,
    file_info: Dict[str, Any],
) -> MainImageAnchor:
    generation_meta = file_info.get("generationMeta") if isinstance(file_info, dict) else {}
    prompt_excerpt = ""
    if isinstance(generation_meta, dict):
        prompt_excerpt = str(generation_meta.get("prompt", "") or "").strip()[:220]

    fallback_summary_zh = "从主图直接继承主体身份、服装产品形态、场景空间和光线关系，作为后续连续性的唯一视觉锚点。"
    subject_summary = prompt_excerpt or fallback_summary_zh
    return {
        "anchor_id": f"mia_{generate(size=8)}",
        "source_file_id": file_id,
        "subject_type": "character_or_product",
        "subject_summary": subject_summary,
        "environment_identity": {
            "scene_type": "inferred_from_main_image",
        },
        "lighting_identity": {
            "lighting_style": "inherit_from_main_image",
        },
        "style_identity": {
            "render_style": "commercial storyboard still",
        },
        "source_prompt_excerpt": prompt_excerpt,
    }


def _build_continuity_bible(anchor: MainImageAnchor) -> ContinuityBible:
    return {
        "continuity_id": f"cb_{generate(size=8)}",
        "anchor_id": anchor.get("anchor_id", ""),
        "hard_constraints": {
            "subject_identity": True,
            "core_wardrobe": True,
            "product_shape": True,
        },
        "soft_constraints": {
            "background_style": "prefer_keep",
            "lighting_style": "prefer_keep",
            "mood": "prefer_keep",
        },
        "allowed_variations": ["camera_view", "framing", "pose", "minor_background_shift"],
    }


def _default_shot_blueprint() -> List[Dict[str, Any]]:
    return [
        {
            "narrative_role": "establishing",
            "shot_goal": "建立主体和场景关系",
            "shot_goal_en": "Establish the hero subject and the scene relationship.",
            "default_view": "front_three_quarter",
            "allowed_views": ["front_three_quarter", "front", "slight_low_angle"],
            "framing": "wide",
            "gaze_target": "book",
            "subject_state": "reading",
            "background_visibility": "high",
            "information_gain": "交代庭院、房屋、烧烤区与主体之间的空间关系。",
            "information_gain_en": "Clarify the spatial relationship between the yard, house, grill area, and hero subject.",
            "must_change_vs_prev": ["framing", "camera_side"],
        },
        {
            "narrative_role": "progression",
            "shot_goal": "推进动作、视线或情绪变化",
            "shot_goal_en": "Advance the action, gaze direction, or emotional beat.",
            "default_view": "medium_close",
            "allowed_views": ["medium_close", "left_front_45", "right_front_45"],
            "framing": "close",
            "gaze_target": "offscreen_right",
            "subject_state": "head_turn",
            "background_visibility": "medium",
            "information_gain": "让主体从静态阅读转向新的注意力方向，形成第二拍推进。",
            "information_gain_en": "Shift the subject from static reading into a new direction of attention to create the next beat.",
            "must_change_vs_prev": ["framing", "gaze_target", "camera_side"],
        },
        {
            "narrative_role": "reaction",
            "shot_goal": "强化情绪、表情或关键动作细节",
            "shot_goal_en": "Tighten focus on emotion, expression, or a key action detail.",
            "default_view": "close_up_focus",
            "allowed_views": ["close_up_focus", "side_profile", "high_angle"],
            "framing": "close",
            "gaze_target": "offscreen_left",
            "subject_state": "attention_shift",
            "background_visibility": "low",
            "information_gain": "把信息重心拉到脸部、情绪和服装细节，而不是环境介绍。",
            "information_gain_en": "Move the emphasis to the face, emotion, and wardrobe detail rather than environmental exposition.",
            "must_change_vs_prev": ["gaze_target", "camera_side"],
        },
        {
            "narrative_role": "closure",
            "shot_goal": "收束为更清晰的 hero 镜头",
            "shot_goal_en": "Resolve into a cleaner, stronger hero composition.",
            "default_view": "hero_front",
            "allowed_views": ["hero_front", "slight_low_angle", "full_body_clean"],
            "framing": "medium",
            "gaze_target": "book",
            "subject_state": "soft_smile",
            "background_visibility": "medium",
            "information_gain": "形成更干净的广告式收束，不重复 opening 的信息。",
            "information_gain_en": "Land on a cleaner advertising-style resolution without repeating the opening information.",
            "must_change_vs_prev": ["camera_side", "subject_state"],
        },
    ]


def _build_storyboard_plan(
    main_image_file_id: str,
    aspect_ratio: str,
    shot_count: int,
    variant_count_per_shot: int,
    continuity_id: str,
) -> StoryboardPlan:
    blueprint = _default_shot_blueprint()
    shots: List[StoryboardShot] = []
    for index in range(shot_count):
        shot_base = blueprint[index] if index < len(blueprint) else blueprint[-1]
        shots.append(
            {
                "shot_id": f"S{index + 1}",
                "order_index": index + 1,
                "narrative_role": str(shot_base["narrative_role"]),
                "shot_goal": str(shot_base["shot_goal"]),
                "shot_goal_en": str(shot_base.get("shot_goal_en", shot_base["shot_goal"])),
                "continuity_anchor": "inherit subject identity, wardrobe, product shape, scene mood, and lighting",
                "default_view": str(shot_base["default_view"]),
                "allowed_views": list(shot_base["allowed_views"]),
                "framing": str(shot_base["framing"]),
                "gaze_target": str(shot_base["gaze_target"]),
                "subject_state": str(shot_base["subject_state"]),
                "background_visibility": str(shot_base["background_visibility"]),
                "information_gain": str(shot_base["information_gain"]),
                "information_gain_en": str(
                    shot_base.get("information_gain_en", shot_base["information_gain"])
                ),
                "must_change_vs_prev": list(shot_base["must_change_vs_prev"]),
            }
        )
    return {
        "storyboard_id": f"sb_{generate(size=8)}",
        "source_main_image_file_id": main_image_file_id,
        "mode": "linear_storyboard",
        "aspect_ratio": aspect_ratio,
        "shot_count": shot_count,
        "variant_count_per_shot": variant_count_per_shot,
        "continuity_id": continuity_id,
        "shots": shots,
    }


def _build_storyboard_prompt_bundle(
    user_prompt: str,
    anchor: MainImageAnchor,
    continuity: ContinuityBible,
    plan: StoryboardPlan,
) -> Dict[str, Any]:
    shot_summaries = []
    for shot in plan.get("shots", []):
        shot_summaries.append(
            f"{shot.get('shot_id')}: {shot.get('shot_goal')} ({shot.get('narrative_role')}, {shot.get('framing')}, 看向 {shot.get('gaze_target')})"
        )

    prompt = (
        f"请基于已选主图生成一组线性分镜，共 {plan.get('shot_count', 4)} 镜。"
        "首轮每镜仅生成 1 个 primary 镜头，优先保证镜头职责差异，再决定是否扩展候选。\n\n"
        f"用户需求：{user_prompt or '基于主图自动扩展分镜'}\n"
        f"主图锚点：{anchor.get('subject_summary', '')}\n"
        f"镜头规划：\n- " + "\n- ".join(shot_summaries)
    )
    return {
        "prompt_bundle_id": f"pb_{generate(size=8)}",
        "task_type": "storyboard_image_generation",
        "prompt": prompt,
        "main_image_summary": {
            "source_main_image_file_id": plan.get("source_main_image_file_id"),
            "subject_summary": anchor.get("subject_summary"),
            "source_prompt_excerpt": anchor.get("source_prompt_excerpt"),
        },
        "continuity_summary": {
            "hard_constraints": list((continuity.get("hard_constraints") or {}).keys()),
            "soft_constraints": continuity.get("soft_constraints"),
            "allowed_variations": continuity.get("allowed_variations"),
        },
        "display_summary": {
            "mode": plan.get("mode"),
            "shot_count": plan.get("shot_count"),
            "variant_count_per_shot": plan.get("variant_count_per_shot"),
            "source_main_image_file_id": plan.get("source_main_image_file_id"),
        },
    }


def _variant_spec_for_index(shot: StoryboardShot, allowed_views: List[str], index: int) -> Dict[str, Any]:
    view = allowed_views[index % len(allowed_views)] if allowed_views else "front_three_quarter"
    narrative_role = str(shot.get("narrative_role", "") or "")
    presets: Dict[str, Dict[str, Any]] = {
        "front_three_quarter": {"azimuth": 35, "elevation": 0, "framing": "wide"},
        "front": {"azimuth": 0, "elevation": 0, "framing": "wide"},
        "slight_low_angle": {"azimuth": 15, "elevation": 20, "framing": "wide"},
        "left_front_45": {"azimuth": 45, "elevation": 0, "framing": "medium"},
        "right_front_45": {"azimuth": -45, "elevation": 0, "framing": "medium"},
        "medium_close": {"azimuth": 20, "elevation": 0, "framing": "close"},
        "close_up_focus": {"azimuth": 0, "elevation": 0, "framing": "close"},
        "side_profile": {"azimuth": 90, "elevation": 0, "framing": "medium"},
        "high_angle": {"azimuth": 0, "elevation": -25, "framing": "medium"},
        "hero_front": {"azimuth": 0, "elevation": 10, "framing": "medium"},
        "full_body_clean": {"azimuth": 0, "elevation": 0, "framing": "full"},
    }
    role_overrides: Dict[str, Dict[str, Dict[str, Any]]] = {
        "establishing": {
            "front_three_quarter": {"framing": "wide"},
            "front": {"framing": "wide"},
            "slight_low_angle": {"framing": "wide"},
        },
        "progression": {
            "left_front_45": {"azimuth": 60, "framing": "medium"},
            "right_front_45": {"azimuth": -60, "framing": "medium"},
            "medium_close": {"azimuth": 55, "framing": "close"},
        },
        "reaction": {
            "close_up_focus": {"framing": "close"},
            "side_profile": {"framing": "medium"},
            "high_angle": {"framing": "medium"},
        },
        "closure": {
            "hero_front": {"framing": "medium"},
            "slight_low_angle": {"framing": "medium"},
            "full_body_clean": {"framing": "full"},
        },
    }
    spec = dict(presets.get(view, {"azimuth": 0, "elevation": 0, "framing": "medium"}))
    spec.update(role_overrides.get(narrative_role, {}).get(view, {}))
    spec["view_type"] = view
    return spec


def _build_storyboard_variant_prompts(
    user_prompt: str,
    anchor: MainImageAnchor,
    shot: StoryboardShot,
    variant_spec: Dict[str, Any],
    aspect_ratio: str,
    previous_shot: Optional[StoryboardShot] = None,
) -> Dict[str, str]:
    shot_id = str(shot.get('shot_id', '') or '')
    narrative_role = str(shot.get('narrative_role', '') or '')
    shot_goal = str(shot.get('shot_goal', '') or '')
    view_type = str(variant_spec.get('view_type', '') or '')
    shot_framing = str(shot.get("framing", variant_spec.get("framing", "medium")) or "medium")
    gaze_target = str(shot.get("gaze_target", "book") or "book")
    subject_state = str(shot.get("subject_state", "reading") or "reading")
    background_visibility = str(shot.get("background_visibility", "medium") or "medium")
    information_gain = str(shot.get("information_gain", "") or "")
    previous_summary = ""
    if previous_shot:
        previous_summary = (
            f"Previous shot: {previous_shot.get('shot_id')} / {previous_shot.get('narrative_role')} / "
            f"{previous_shot.get('framing')} / gaze {previous_shot.get('gaze_target')}."
        )

    role_specific_instruction = (
        "Keep the shot visually distinct from neighboring storyboard frames while staying inside the same scene."
    )
    if narrative_role == "establishing":
        role_specific_instruction = (
            "This is the opening keyframe. Re-establish the full scene relationship clearly. If the reference image is already a medium hero frame, pull one step wider so the location and supporting action read more clearly while the hero subject still anchors the frame."
        )
    elif narrative_role == "progression":
        role_specific_instruction = (
            "This is the progression shot. Keep the same scene, but create a clearly different frame by changing the subject's gaze direction, head turn, upper-body angle, or hand/object relationship. If the reference image shows the hero looking down or resting in a static pose, lift their attention into a new direction so the frame feels like the next beat, not a tiny variation of the same still."
        )
    elif narrative_role == "reaction":
        role_specific_instruction = (
            "This is the feature-focus shot. Stay in the same scene while tightening emphasis on the hero subject, garment, facial expression, or a specific action/detail moment. Crop closer than the opening or progression shot, but leave enough environmental evidence to prove continuity."
        )
    elif narrative_role == "closure":
        role_specific_instruction = (
            "This is the resolution shot. Keep the same scene and subject, but land on a cleaner hero composition with stronger closure. Avoid ending on a near-duplicate of the opening frame; the final image should feel more resolved and deliberate."
        )

    framing_specific_instruction = (
        "Keep composition consistent with the requested framing."
    )
    if view_type in {"left_front_45", "right_front_45", "side_profile"}:
        framing_specific_instruction = (
            "Make the camera shift readable: the face, shoulder line, and chair/background perspective should reflect the requested side angle instead of repeating the original straight-on composition."
        )
    elif view_type in {"medium_close", "close_up_focus"}:
        framing_specific_instruction = (
            "Move tighter into the hero subject while preserving enough background evidence to prove this is the same location. The face direction, shoulder line, and what the hands are doing should read differently from the reference image."
        )
    elif view_type in {"front_three_quarter", "front", "hero_front"}:
        framing_specific_instruction = (
            "Do not simply repeat the reference crop. Make the camera distance and subject-to-background relationship readable at a glance."
        )
    elif variant_spec.get("framing") == "wide":
        framing_specific_instruction = (
            "Open the frame up enough that the environment and any supporting in-scene action become more readable than in the reference image."
        )
    elif variant_spec.get("framing") == "full":
        framing_specific_instruction = (
            "Show a fuller-body hero composition with a cleaner silhouette and a visibly different crop from the earlier frames."
        )

    prompt = (
        f"{shot_id} 分镜候选，职责：{shot_goal}。"
        f"机位：{view_type}，景别：{variant_spec.get('framing')}。"
        f"人物状态：{subject_state}，视线：{gaze_target}。"
        "保持主图中的主体身份、服装、产品形态、场景情绪和灯光逻辑连续。\n"
        f"补充要求：{user_prompt or '基于主图自动扩展分镜'}\n"
        f"主图锚点：{anchor.get('subject_summary', '')}"
    )
    return {
        "prompt": (
            prompt
            + "\n"
            + f"Shot role: {narrative_role}\n"
            + f"Camera view: {view_type}\n"
            + f"Azimuth: {variant_spec.get('azimuth')} degrees\n"
            + f"Elevation: {variant_spec.get('elevation')} degrees\n"
            + f"Framing: {shot_framing}\n"
            + f"Aspect ratio: {aspect_ratio}\n"
            + f"Gaze target: {gaze_target}\n"
            + f"Subject state: {subject_state}\n"
            + f"Background visibility: {background_visibility}\n"
            + f"Information gain: {information_gain}\n"
            + "Keep strict continuity with the attached main image for subject identity, hairstyle, wardrobe, product shape, scene mood, lighting, and background architecture.\n"
            + "This must remain the same scene, the same world state, and the same shoot family as the main image.\n"
            + "Do not invent a different room, different outdoor location, different supporting cast, different styling concept, or different time of day.\n"
            + "If the reference image contains supporting people, furniture, props, or architectural cues, preserve them when they reasonably remain in frame.\n"
            + "Change only the camera position, framing, subject pose, and attention focus required by this shot.\n"
            + "Each storyboard shot must be immediately distinguishable from the previous one in either framing scale, gaze direction, body angle, or camera azimuth. Avoid near-duplicate outputs.\n"
            + (previous_summary + "\n" if previous_summary else "")
            + f"{role_specific_instruction}\n"
            + f"{framing_specific_instruction}\n"
            + "The result should feel like another frame from the same shoot, not a new creative concept.\n"
            + "Produce a professional storyboard still, not a generic pretty image."
        ),
    }


def _evaluate_storyboard_candidate(
    shot: StoryboardShot,
    previous_shot: Optional[StoryboardShot],
    variant_spec: Dict[str, Any],
) -> ShotEvaluationResult:
    reasons: List[str] = []
    score = 100
    current_framing = str(variant_spec.get("framing", shot.get("framing", "medium")) or "medium")
    current_view_type = str(variant_spec.get("view_type", "") or "")
    current_gaze = str(shot.get("gaze_target", "") or "")

    if previous_shot:
        previous_framing = str(previous_shot.get("framing", "") or "")
        previous_view = str(previous_shot.get("default_view", "") or "")
        previous_gaze = str(previous_shot.get("gaze_target", "") or "")
        changed_dimensions = 0
        if current_framing != previous_framing:
            changed_dimensions += 1
        if current_view_type != previous_view:
            changed_dimensions += 1
        if current_gaze != previous_gaze:
            changed_dimensions += 1
        if changed_dimensions < 2:
            reasons.append("insufficient_delta_vs_previous")
            score -= 60

    if shot.get("narrative_role") == "establishing" and current_framing != "wide":
        reasons.append("establishing_not_wide")
        score -= 30
    if shot.get("narrative_role") == "progression" and current_gaze == "book":
        reasons.append("progression_gaze_static")
        score -= 30
    if shot.get("narrative_role") == "reaction" and current_framing not in {"close", "medium"}:
        reasons.append("reaction_not_close_enough")
        score -= 20
    if shot.get("narrative_role") == "closure" and current_view_type == "front_three_quarter":
        reasons.append("closure_too_close_to_opening")
        score -= 20

    return {
        "accepted": score >= 60 and not reasons,
        "reasons": reasons,
        "score": score,
    }


def _select_storyboard_primary_variant(
    shot: StoryboardShot,
    previous_shot: Optional[StoryboardShot],
) -> Dict[str, Any]:
    allowed_views = list(shot.get("allowed_views", []) or [])
    if not allowed_views:
        allowed_views = [
            str(shot.get("default_view", "front_three_quarter") or "front_three_quarter")
        ]

    evaluated_specs: List[Dict[str, Any]] = []
    for index, _ in enumerate(allowed_views):
        variant_spec = _variant_spec_for_index(shot, allowed_views, index)
        evaluation = _evaluate_storyboard_candidate(shot, previous_shot, variant_spec)
        evaluated_specs.append(
            {
                "variant_spec": variant_spec,
                "evaluation": evaluation,
                "attempt_index": index,
            }
        )

    accepted_spec = next(
        (
            item
            for item in evaluated_specs
            if bool(item["evaluation"].get("accepted"))
        ),
        None,
    )
    if accepted_spec:
        return accepted_spec

    return max(
        evaluated_specs,
        key=lambda item: int(item["evaluation"].get("score", 0) or 0),
    )

def _extract_existing_storyboard_meta(file_info: Dict[str, Any]) -> Dict[str, Any]:
    storyboard_meta = file_info.get("storyboardMeta")
    return storyboard_meta if isinstance(storyboard_meta, dict) else {}


def _next_variant_index(canvas_data: Dict[str, Any], shot_id: str) -> int:
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        return 1
    count = 0
    for file_info in files.values():
        if not isinstance(file_info, dict):
            continue
        meta = file_info.get("storyboardMeta")
        if isinstance(meta, dict) and str(meta.get("shot_id", "")) == shot_id:
            count += 1
    return max(count + 1, 1)


def _build_multiview_prompt_bundle(
    source_meta: Dict[str, Any],
    azimuth: int,
    elevation: int,
    framing: str,
    preset_name: str,
) -> Dict[str, Any]:
    shot_family_id = str(source_meta.get("shot_family_id", "") or "")
    prompt = (
        f"基于当前镜头家族生成一个新的多视角候选。预设：{preset_name or '自定义'}，"
        f"水平环绕：{azimuth}°，垂直俯仰：{elevation}°，景别：{framing}。"
        "保持主体身份、服装、产品形态和整体画面气质连续，但必须形成明确可读的机位差异。"
    )
    return {
        "prompt_bundle_id": f"pb_{generate(size=8)}",
        "task_type": "multiview_variant_generation",
        "shot_family_id": shot_family_id,
        "prompt": prompt,
        "display_summary": {
            "source_shot_id": source_meta.get("shot_id"),
            "preset_name": preset_name or "custom",
            "azimuth": azimuth,
            "elevation": elevation,
            "framing": framing,
        },
    }


def _build_multiview_execution_prompt(
    prompt_bundle: Dict[str, Any],
    source_meta: Dict[str, Any],
    user_prompt: str,
) -> str:
    context_text = user_prompt or str(source_meta.get("summary", "") or "")
    return (
        str(prompt_bundle.get("prompt") or "")
        + "\n"
        + f"Shot role: {source_meta.get('narrative_role', 'generic_storyboard_frame')}\n"
        + f"Shot family id: {source_meta.get('shot_family_id', 'inherit_from_source')}\n"
        + f"Original request context: {context_text}\n"
        + "Keep the same exact scene family, wardrobe/product appearance, lighting logic, and visual identity as the reference image.\n"
        + "Do not restyle the scene or replace the environment; this is a camera variation of the same shot family.\n"
        + "The new frame must read as a clearly different camera placement or framing scale, not a tiny perturbation of the same crop.\n"
        + "Produce a clean storyboard still rather than a heavily stylized reinterpretation."
    )


def _parse_angle(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_framing(value: Any) -> str:
    framing = str(value or "").strip().lower()
    if framing in {"close", "medium", "full", "wide"}:
        return framing
    return "medium"


def _normalize_preset_name(value: Any) -> str:
    return str(value or "").strip()


def _preferred_position_from_anchor(
    source_element: Dict[str, Any],
    shot_index: int,
    variant_index: int,
) -> Optional[Dict[str, float]]:
    if not source_element:
        return None
    source_x = float(source_element.get("x", 0) or 0)
    source_y = float(source_element.get("y", 0) or 0)
    source_width = float(source_element.get("width", 360) or 360)
    source_height = float(source_element.get("height", 360) or 360)
    gap = 24.0
    return {
        "x": source_x + (variant_index * (source_width + gap)),
        "y": source_y + source_height + 48.0 + (shot_index * (source_height + gap)),
    }


def _preferred_position_for_shot_append(
    canvas_data: Dict[str, Any],
    storyboard_id: str,
    shot_id: str,
    source_element: Dict[str, Any],
) -> Optional[Dict[str, float]]:
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    elements = canvas_data.get("elements", []) if isinstance(canvas_data, dict) else []
    if not isinstance(files, dict) or not isinstance(elements, list):
        return None

    matched_elements: List[Dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        if element.get("type") != "image":
            continue

        file_id = str(element.get("fileId", "") or "")
        file_info = files.get(file_id)
        if not isinstance(file_info, dict):
            continue

        storyboard_meta = file_info.get("storyboardMeta")
        if not isinstance(storyboard_meta, dict):
            continue
        if str(storyboard_meta.get("shot_id", "") or "") != shot_id:
            continue
        if storyboard_id and str(storyboard_meta.get("storyboard_id", "") or "") != storyboard_id:
            continue

        matched_elements.append(element)

    if matched_elements:
        rightmost_element = max(
            matched_elements,
            key=lambda element: float(element.get("x", 0) or 0)
            + float(element.get("width", 0) or 0),
        )
        return {
            "x": float(rightmost_element.get("x", 0) or 0)
            + float(rightmost_element.get("width", 360) or 360)
            + 24.0,
            "y": float(rightmost_element.get("y", 0) or 0),
        }

    if source_element:
        return {
            "x": float(source_element.get("x", 0) or 0)
            + float(source_element.get("width", 360) or 360)
            + 24.0,
            "y": float(source_element.get("y", 0) or 0),
        }

    return None


async def handle_direct_storyboard(data: Dict[str, Any]) -> None:
    messages = _normalize_messages(data)
    session_id = str(data.get("session_id", "") or "")
    canvas_id = str(data.get("canvas_id", "") or "")
    prompt = _normalize_prompt(data)
    main_image_file_id = _normalize_main_image_file_id(data)
    reference_image_file_id = _normalize_reference_image_file_id(data, "reference_image_file_id")
    aspect_ratio = _normalize_aspect_ratio(data)
    shot_count = _normalize_shot_count(data)
    variant_count = _normalize_variant_count(data)
    image_tool_id = _normalize_tool_id(data)

    if not session_id or not canvas_id or not main_image_file_id:
        raise RuntimeError("Storyboard generation requires session_id, canvas_id, and main_image_file_id.")

    existing_task = get_stream_task(session_id)
    if existing_task and not existing_task.done():
        await send_to_websocket(
            session_id,
            {"type": "info", "info": "当前任务仍在进行中，请等待完成后再生成分镜。"},
        )
        return

    if messages:
        await db_service.create_message(session_id, messages[-1].get("role", "user"), json.dumps(messages[-1]))

    task = asyncio.create_task(
        _process_direct_storyboard(
            session_id=session_id,
            canvas_id=canvas_id,
            prompt=prompt,
            main_image_file_id=main_image_file_id,
            reference_image_file_id=reference_image_file_id,
            aspect_ratio=aspect_ratio,
            shot_count=shot_count,
            variant_count=variant_count,
            image_tool_id=image_tool_id,
            messages=messages,
        )
    )
    add_stream_task(session_id, task)
    try:
        await task
    finally:
        remove_stream_task(session_id)
        await send_to_websocket(session_id, {"type": "done"})


async def _process_direct_storyboard(
    session_id: str,
    canvas_id: str,
    prompt: str,
    main_image_file_id: str,
    reference_image_file_id: str,
    aspect_ratio: str,
    shot_count: int,
    variant_count: int,
    image_tool_id: str,
    messages: List[Dict[str, Any]],
) -> None:
    response = await create_direct_storyboard_response(
        session_id=session_id,
        canvas_id=canvas_id,
        prompt=prompt,
        main_image_file_id=main_image_file_id,
        reference_image_file_id=reference_image_file_id,
        aspect_ratio=aspect_ratio,
        shot_count=shot_count,
        variant_count=variant_count,
        image_tool_id=image_tool_id,
    )
    await db_service.create_message(session_id, "assistant", json.dumps(response))
    await send_to_websocket(session_id, {"type": "all_messages", "messages": messages + [response]})


async def create_direct_storyboard_response(
    session_id: str,
    canvas_id: str,
    prompt: str,
    main_image_file_id: str,
    reference_image_file_id: str,
    aspect_ratio: str,
    shot_count: int,
    variant_count: int,
    image_tool_id: str,
) -> Dict[str, Any]:
    canvas_data = await _load_canvas_context(canvas_id)
    file_info = _get_canvas_file(canvas_data, main_image_file_id)
    source_element = _get_canvas_image_element(canvas_data, main_image_file_id)
    image_tool = _resolve_reference_tool(image_tool_id)
    reference_file_id = reference_image_file_id or main_image_file_id
    anchor = _build_main_image_anchor(main_image_file_id, file_info)
    continuity = _build_continuity_bible(anchor)
    continuity_asset = build_continuity_asset(
        main_image_file_id=main_image_file_id,
        anchor=anchor,
        continuity_bible=continuity,
        prompt=prompt,
    )
    await upsert_continuity_asset(canvas_id, continuity_asset, set_current=True)
    continuity_prompt_bundle = {
        "prompt_bundle_id": f"pb_{generate(size=8)}",
        "task_type": "continuity_asset_confirmation",
        "prompt": str(continuity_asset.get("prompt", "") or ""),
        "main_image_summary": continuity_asset.get("main_image_summary", {}),
        "continuity_summary": continuity_asset.get("continuity_summary", {}),
        "display_summary": {
            "source_main_image_file_id": main_image_file_id,
            "status": continuity_asset.get("status", "draft"),
            "version": continuity_asset.get("version", 1),
        },
        "continuity_asset": continuity_asset,
    }
    continuity_confirmation_status = await request_prompt_bundle_confirmation(
        session_id=session_id,
        tool_name="generate_storyboard_from_main_image",
        payload=continuity_prompt_bundle,
    )
    if continuity_confirmation_status == "revise":
        return {
            "role": "assistant",
            "content": "已返回修改，请先调整主图 continuity 约束后重新提交。",
        }
    if continuity_confirmation_status != "confirmed":
        return {
            "role": "assistant",
            "content": "已取消主图 continuity 确认。",
        }

    continuity_asset["status"] = "confirmed"
    continuity_asset["updated_at"] = continuity_asset.get("updated_at")
    await upsert_continuity_asset(canvas_id, continuity_asset, set_current=True)
    plan = _build_storyboard_plan(
        main_image_file_id=main_image_file_id,
        aspect_ratio=aspect_ratio,
        shot_count=shot_count,
        variant_count_per_shot=variant_count,
        continuity_id=str(continuity.get("continuity_id", "")),
    )
    storyboard_plan_asset = build_storyboard_plan_asset(
        continuity_asset=continuity_asset,
        storyboard_plan=plan,
        prompt=prompt,
    )
    await upsert_storyboard_plan(canvas_id, storyboard_plan_asset)
    prompt_bundle = _build_storyboard_prompt_bundle(
        prompt,
        anchor,
        continuity,
        plan,
    )
    prompt_bundle["storyboard_plan"] = storyboard_plan_asset

    confirmation_status = await request_prompt_bundle_confirmation(
        session_id=session_id,
        tool_name="generate_storyboard_from_main_image",
        payload=prompt_bundle,
    )
    if confirmation_status == "revise":
        return {
            "role": "assistant",
            "content": "已返回修改，请调整分镜参数后重新提交。",
        }
    if confirmation_status != "confirmed":
        return {
            "role": "assistant",
            "content": "已取消主图分镜生成。",
        }
    storyboard_plan_asset["status"] = "confirmed"
    await upsert_storyboard_plan(canvas_id, storyboard_plan_asset)

    await send_to_websocket(
        session_id,
        {
            "type": "info",
            "info": (
                f"正在基于主图生成 {shot_count} 镜分镜。"
                "首轮每镜先生成 1 个 primary 镜头，确认镜头差异后再扩展候选。"
            ),
        },
    )

    previous_primary_shot: Optional[StoryboardShot] = None
    primary_variant_count = _primary_variant_budget(variant_count)
    for shot_index, shot in enumerate(plan.get("shots", [])):
        selected_primary = _select_storyboard_primary_variant(shot, previous_primary_shot)
        variant_spec = selected_primary["variant_spec"]
        shot_evaluation = selected_primary["evaluation"]
        variant_zero_index = 0
        variant_id = f"{shot.get('shot_id')}V{variant_zero_index + 1}"
        shot_family_id = _build_shot_family_id(str(plan["storyboard_id"]), str(shot["shot_id"]))
        variant_prompts = _build_storyboard_variant_prompts(
            prompt,
            anchor,
            shot,
            variant_spec,
            aspect_ratio,
            previous_shot=previous_primary_shot,
        )
        await generate_image_with_provider(
            canvas_id=canvas_id,
            session_id=session_id,
            provider=image_tool["provider"],
            model=image_tool["model"],
            prompt=variant_prompts["prompt"],
            aspect_ratio=aspect_ratio,
            input_images=[reference_file_id],
            metadata_overrides={
                "tool_id": image_tool["tool_id"],
                "prompt_bundle_id": prompt_bundle["prompt_bundle_id"],
                "prompt": variant_prompts["prompt"],
                "main_image_file_id": main_image_file_id,
                "reference_image_file_id": reference_file_id,
                "storyboard_id": plan["storyboard_id"],
            },
            storyboard_metadata_overrides={
                "storyboard_id": plan["storyboard_id"],
                "shot_family_id": shot_family_id,
                "continuity_version": continuity_asset.get("version", 1),
                "shot_id": shot["shot_id"],
                "variant_id": variant_id,
                "source_main_image_file_id": main_image_file_id,
                "continuity_id": continuity["continuity_id"],
                "source_variant_id": "",
                "generation_mode": "storyboard",
                "generation_pass": "primary_first",
                "narrative_role": shot["narrative_role"],
                "shot_goal": shot["shot_goal"],
                "view_type": variant_spec["view_type"],
                "azimuth": variant_spec["azimuth"],
                "elevation": variant_spec["elevation"],
                "framing": variant_spec["framing"],
                "gaze_target": shot.get("gaze_target", "book"),
                "subject_state": shot.get("subject_state", "reading"),
                "background_visibility": shot.get("background_visibility", "medium"),
                "information_gain": shot.get("information_gain", ""),
                "must_change_vs_prev": list(shot.get("must_change_vs_prev", []) or []),
                "camera_target": {
                    "azimuth": variant_spec["azimuth"],
                    "elevation": variant_spec["elevation"],
                    "framing": variant_spec["framing"],
                    "preset_name": variant_spec["view_type"],
                },
                "camera_state": _build_camera_state(
                    preset_name=str(variant_spec["view_type"]),
                    view_type=str(variant_spec["view_type"]),
                    azimuth=int(variant_spec["azimuth"]),
                    elevation=int(variant_spec["elevation"]),
                    framing=str(variant_spec["framing"]),
                ),
                "is_primary_variant": True,
                "variant_count": variant_count,
                "primary_variant_count": primary_variant_count,
                "shot_evaluation": shot_evaluation,
                "prompt_snapshot": variant_prompts["prompt"],
            },
            preferred_position=_preferred_position_from_anchor(
                source_element,
                shot_index,
                variant_zero_index,
            ),
        )
        previous_primary_shot = shot

    return {
        "role": "assistant",
        "content": (
            f"已基于主图生成 {shot_count} 镜线性分镜。"
            "首轮每镜已生成 1 个 primary 镜头，并按 shot family 结构回写到画布中。"
        ),
    }


async def handle_direct_multiview(data: Dict[str, Any]) -> None:
    messages = _normalize_messages(data)
    session_id = str(data.get("session_id", "") or "")
    canvas_id = str(data.get("canvas_id", "") or "")
    source_file_id = str(data.get("source_file_id", "") or "").strip()
    reference_image_file_id = _normalize_reference_image_file_id(data, "reference_image_file_id")
    image_tool_id = _normalize_tool_id(data)
    aspect_ratio = _normalize_aspect_ratio(data)
    preview_only = _normalize_preview_only(data)
    replace_source = _normalize_replace_source(data)

    if not session_id or not canvas_id or not source_file_id:
        raise RuntimeError("Multiview generation requires session_id, canvas_id, and source_file_id.")

    existing_task = get_stream_task(session_id)
    if existing_task and not existing_task.done():
        await send_to_websocket(
            session_id,
            {"type": "info", "info": "当前任务仍在进行中，请等待完成后再生成多视角候选。"},
        )
        return

    if messages:
        await db_service.create_message(session_id, messages[-1].get("role", "user"), json.dumps(messages[-1]))

    task = asyncio.create_task(
        _process_direct_multiview(
            session_id=session_id,
            canvas_id=canvas_id,
            source_file_id=source_file_id,
            reference_image_file_id=reference_image_file_id,
            prompt=_normalize_prompt(data),
            image_tool_id=image_tool_id,
            aspect_ratio=aspect_ratio,
            preview_only=preview_only,
            replace_source=replace_source,
            preset_name=_normalize_preset_name(data.get("preset_name")),
            azimuth=_parse_angle(data.get("azimuth"), 45),
            elevation=_parse_angle(data.get("elevation"), 0),
            framing=_normalize_framing(data.get("framing")),
            messages=messages,
        )
    )
    add_stream_task(session_id, task)
    try:
        await task
    finally:
        remove_stream_task(session_id)
        await send_to_websocket(session_id, {"type": "done"})


async def _process_direct_multiview(
    session_id: str,
    canvas_id: str,
    source_file_id: str,
    reference_image_file_id: str,
    prompt: str,
    image_tool_id: str,
    aspect_ratio: str,
    preview_only: bool,
    replace_source: bool,
    preset_name: str,
    azimuth: int,
    elevation: int,
    framing: str,
    messages: List[Dict[str, Any]],
) -> None:
    response = await create_direct_multiview_response(
        session_id=session_id,
        canvas_id=canvas_id,
        source_file_id=source_file_id,
        reference_image_file_id=reference_image_file_id,
        prompt=prompt,
        image_tool_id=image_tool_id,
        aspect_ratio=aspect_ratio,
        preview_only=preview_only,
        replace_source=replace_source,
        preset_name=preset_name,
        azimuth=azimuth,
        elevation=elevation,
        framing=framing,
    )
    await db_service.create_message(session_id, "assistant", json.dumps(response))
    await send_to_websocket(session_id, {"type": "all_messages", "messages": messages + [response]})


async def create_direct_multiview_response(
    session_id: str,
    canvas_id: str,
    source_file_id: str,
    reference_image_file_id: str,
    prompt: str,
    image_tool_id: str,
    aspect_ratio: str,
    preview_only: bool,
    replace_source: bool,
    preset_name: str,
    azimuth: int,
    elevation: int,
    framing: str,
) -> Dict[str, Any]:
    canvas_data = await _load_canvas_context(canvas_id)
    file_info = _get_canvas_file(canvas_data, source_file_id)
    source_element = _get_canvas_image_element(canvas_data, source_file_id)
    source_meta = _extract_existing_storyboard_meta(file_info)
    continuity_asset = await get_current_continuity_asset(canvas_id)
    image_tool = _resolve_reference_tool(image_tool_id)
    reference_file_id = reference_image_file_id or source_file_id
    existing_file_ids = (
        set(canvas_data.get("files", {}).keys())
        if isinstance(canvas_data.get("files", {}), dict)
        else set()
    )
    source_shot_id = str(source_meta.get("shot_id", "") or "")
    if not source_shot_id:
        source_shot_id = f"S_{source_file_id}"
    shot_family_id = str(source_meta.get("shot_family_id", "") or "") or _build_shot_family_id(
        str(source_meta.get("storyboard_id", f"sb_{source_file_id}") or f"sb_{source_file_id}"),
        source_shot_id,
    )
    prompt_bundle = _build_multiview_prompt_bundle(source_meta, azimuth, elevation, framing, preset_name)
    execution_prompt = _build_multiview_execution_prompt(prompt_bundle, source_meta, prompt)
    confirmation_status = await request_prompt_bundle_confirmation(
        session_id=session_id,
        tool_name="generate_multiview_variant",
        payload={
            **prompt_bundle,
            "shot_family_id": shot_family_id,
            "target_id": shot_family_id,
        },
    )
    if confirmation_status == "revise":
        return {
            "role": "assistant",
            "content": "已返回修改，请调整多视角参数后重新提交。",
        }
    if confirmation_status != "confirmed":
        return {
            "role": "assistant",
            "content": "已取消多视角候选生成。",
        }
    next_variant_number = _next_variant_index(canvas_data, source_shot_id)
    variant_id = f"{source_shot_id}V{next_variant_number}"

    await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider=image_tool["provider"],
        model=image_tool["model"],
        prompt=execution_prompt,
        aspect_ratio=aspect_ratio,
        input_images=[reference_file_id],
        metadata_overrides={
            "tool_id": image_tool["tool_id"],
            "prompt_bundle_id": prompt_bundle["prompt_bundle_id"],
            "prompt": prompt_bundle["prompt"],
            "preview_only": preview_only,
            "source_file_id": source_file_id,
            "reference_image_file_id": reference_file_id,
        },
        storyboard_metadata_overrides={
            "storyboard_id": str(source_meta.get("storyboard_id", f"sb_{source_file_id}") or f"sb_{source_file_id}"),
            "shot_family_id": shot_family_id,
            "shot_id": source_shot_id,
            "variant_id": variant_id,
            "source_main_image_file_id": str(source_meta.get("source_main_image_file_id", source_file_id) or source_file_id),
            "continuity_id": str(source_meta.get("continuity_id", f"cb_{source_file_id}") or f"cb_{source_file_id}"),
            "continuity_version": int(
                source_meta.get(
                    "continuity_version",
                    (continuity_asset or {}).get("version", 1),
                )
                or 1
            ),
            "narrative_role": str(source_meta.get("narrative_role", "generic_storyboard_frame") or "generic_storyboard_frame"),
            "shot_goal": str(source_meta.get("shot_goal", "Generate a new multiview candidate while preserving continuity.") or "Generate a new multiview candidate while preserving continuity."),
            "view_type": preset_name or "custom",
            "azimuth": azimuth,
            "elevation": elevation,
            "framing": framing,
            "source_variant_id": str(source_meta.get("variant_id", "") or ""),
            "generation_mode": "multiview",
            "generation_pass": "camera_variation",
            "camera_target": {
                "azimuth": azimuth,
                "elevation": elevation,
                "framing": framing,
                "preset_name": preset_name or "custom",
            },
            "camera_state": _build_camera_state(
                preset_name=preset_name or "custom",
                view_type=preset_name or "custom",
                azimuth=azimuth,
                elevation=elevation,
                framing=framing,
            ),
            "gaze_target": str(source_meta.get("gaze_target", "") or ""),
            "subject_state": str(source_meta.get("subject_state", "") or ""),
            "background_visibility": str(source_meta.get("background_visibility", "") or ""),
            "information_gain": str(source_meta.get("information_gain", "") or ""),
            "must_change_vs_prev": list(source_meta.get("must_change_vs_prev", []) or []),
            "is_primary_variant": False,
            "prompt_snapshot": execution_prompt,
            "summary": str(source_meta.get("summary", "") or ""),
        },
        preferred_position=_preferred_position_for_shot_append(
            canvas_data=canvas_data,
            storyboard_id=str(
                source_meta.get("storyboard_id", f"sb_{source_file_id}")
                or f"sb_{source_file_id}"
            ),
            shot_id=source_shot_id,
            source_element=source_element,
        ),
    )

    if replace_source:
        refreshed_canvas = await _load_canvas_context(canvas_id)
        refreshed_files = refreshed_canvas.get("files", {}) if isinstance(refreshed_canvas, dict) else {}
        refreshed_elements = refreshed_canvas.get("elements", []) if isinstance(refreshed_canvas, dict) else []
        if isinstance(refreshed_files, dict) and isinstance(refreshed_elements, list):
            new_file_ids = [file_id for file_id in refreshed_files.keys() if file_id not in existing_file_ids]
            if new_file_ids:
                replacement_file_id = new_file_ids[-1]
                replacement_element = None
                source_element_index = None
                replacement_element_index = None
                for index, element in enumerate(refreshed_elements):
                    if not isinstance(element, dict):
                        continue
                    if str(element.get("fileId", "") or "") == source_file_id:
                        source_element_index = index
                    if str(element.get("fileId", "") or "") == replacement_file_id:
                        replacement_element = element
                        replacement_element_index = index

                if source_element_index is not None and replacement_element:
                    source_element = refreshed_elements[source_element_index]
                    if isinstance(source_element, dict):
                        source_element["fileId"] = replacement_file_id
                        source_element["width"] = replacement_element.get("width", source_element.get("width"))
                        source_element["height"] = replacement_element.get("height", source_element.get("height"))
                    if replacement_element_index is not None:
                        refreshed_elements.pop(replacement_element_index)
                    await db_service.save_canvas_data(canvas_id, json.dumps(refreshed_canvas))

    return {
        "role": "assistant",
        "content": (
            "已替换当前图并保留连续性约束。"
            if replace_source
            else "已生成新的多视角候选，并回写到当前镜头组附近。"
        ),
    }


async def handle_direct_storyboard_refine(data: Dict[str, Any]) -> None:
    messages = _normalize_messages(data)
    session_id = str(data.get("session_id", "") or "")
    canvas_id = str(data.get("canvas_id", "") or "")
    source_file_id = str(data.get("source_file_id", "") or "").strip()
    reference_image_file_id = _normalize_reference_image_file_id(data, "reference_image_file_id")
    image_tool_id = _normalize_tool_id(data)
    aspect_ratio = _normalize_aspect_ratio(data)
    mode = _normalize_mode(data, "append")

    if not session_id or not canvas_id or not source_file_id:
        raise RuntimeError("Storyboard refinement requires session_id, canvas_id, and source_file_id.")

    existing_task = get_stream_task(session_id)
    if existing_task and not existing_task.done():
        await send_to_websocket(
            session_id,
            {"type": "info", "info": "当前任务仍在进行中，请等待完成后再编辑当前镜头。"},
        )
        return

    if messages:
        await db_service.create_message(session_id, messages[-1].get("role", "user"), json.dumps(messages[-1]))

    task = asyncio.create_task(
        _process_direct_storyboard_refine(
            session_id=session_id,
            canvas_id=canvas_id,
            source_file_id=source_file_id,
            reference_image_file_id=reference_image_file_id,
            prompt=_normalize_prompt(data),
            image_tool_id=image_tool_id,
            aspect_ratio=aspect_ratio,
            mode=mode,
            messages=messages,
        )
    )
    add_stream_task(session_id, task)
    try:
        await task
    finally:
        remove_stream_task(session_id)
        await send_to_websocket(session_id, {"type": "done"})


async def _process_direct_storyboard_refine(
    session_id: str,
    canvas_id: str,
    source_file_id: str,
    reference_image_file_id: str,
    prompt: str,
    image_tool_id: str,
    aspect_ratio: str,
    mode: str,
    messages: List[Dict[str, Any]],
) -> None:
    response = await create_direct_storyboard_refine_response(
        session_id=session_id,
        canvas_id=canvas_id,
        source_file_id=source_file_id,
        reference_image_file_id=reference_image_file_id,
        prompt=prompt,
        image_tool_id=image_tool_id,
        aspect_ratio=aspect_ratio,
        mode=mode,
    )
    await db_service.create_message(session_id, "assistant", json.dumps(response))
    await send_to_websocket(session_id, {"type": "all_messages", "messages": messages + [response]})


async def create_direct_storyboard_refine_response(
    session_id: str,
    canvas_id: str,
    source_file_id: str,
    reference_image_file_id: str,
    prompt: str,
    image_tool_id: str,
    aspect_ratio: str,
    mode: str,
) -> Dict[str, Any]:
    canvas_data = await _load_canvas_context(canvas_id)
    file_info = _get_canvas_file(canvas_data, source_file_id)
    source_element = _get_canvas_image_element(canvas_data, source_file_id)
    source_meta = _extract_existing_storyboard_meta(file_info)
    continuity_asset = await get_current_continuity_asset(canvas_id)
    image_tool = _resolve_reference_tool(image_tool_id)
    reference_file_id = reference_image_file_id or source_file_id
    existing_file_ids = (
        set(canvas_data.get("files", {}).keys())
        if isinstance(canvas_data.get("files", {}), dict)
        else set()
    )
    source_shot_id = str(source_meta.get("shot_id", "") or "")
    if not source_shot_id:
        source_shot_id = f"S_{source_file_id}"
    shot_family_id = str(source_meta.get("shot_family_id", "") or "") or _build_shot_family_id(
        str(source_meta.get("storyboard_id", f"sb_{source_file_id}") or f"sb_{source_file_id}"),
        source_shot_id,
    )
    next_variant_number = _next_variant_index(canvas_data, source_shot_id)
    variant_id = f"{source_shot_id}V{next_variant_number}"
    prompt_text = (
        f"对当前镜头进行单镜优化，保持主体身份、服装、产品形态、场景与灯光连续。\n"
        f"修改意图：{prompt or '在当前 shot 下生成一个更合适的候选'}"
    )
    execution_prompt = (
        prompt_text
        + "\n"
        + "Refine the attached storyboard frame while preserving the same subject, wardrobe, product appearance, scene family, and lighting logic.\n"
        + f"Refinement intent: {prompt or 'Generate a stronger candidate inside the same storyboard shot.'}\n"
        + "Keep the same location, same background family, same supporting cast/props when visible, and same time-of-day feeling.\n"
        + "Do not change to a new scene. Keep this as the same storyboard shot."
    )
    confirmation_status = await request_prompt_bundle_confirmation(
        session_id=session_id,
        tool_name="generate_multiview_variant",
        payload={
            "prompt_bundle_id": f"pb_{generate(size=8)}",
            "task_type": "storyboard_refinement",
            "target_id": shot_family_id,
            "prompt": prompt_text,
            "display_summary": {
                "source_file_id": source_file_id,
                "shot_id": source_shot_id,
                "shot_family_id": shot_family_id,
                "mode": mode,
            },
        },
    )
    if confirmation_status == "revise":
        return {
            "role": "assistant",
            "content": "已返回修改，请调整单镜优化意图后重新提交。",
        }
    if confirmation_status != "confirmed":
        return {
            "role": "assistant",
            "content": "已取消单镜优化。",
        }

    await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider=image_tool["provider"],
        model=image_tool["model"],
        prompt=execution_prompt,
        aspect_ratio=aspect_ratio,
        input_images=[reference_file_id],
        metadata_overrides={
            "tool_id": image_tool["tool_id"],
            "prompt": prompt_text,
            "source_file_id": source_file_id,
            "reference_image_file_id": reference_file_id,
        },
        storyboard_metadata_overrides={
            "storyboard_id": str(source_meta.get("storyboard_id", f"sb_{source_file_id}") or f"sb_{source_file_id}"),
            "shot_family_id": shot_family_id,
            "shot_id": source_shot_id,
            "variant_id": variant_id,
            "source_main_image_file_id": str(source_meta.get("source_main_image_file_id", source_file_id) or source_file_id),
            "continuity_id": str(source_meta.get("continuity_id", f"cb_{source_file_id}") or f"cb_{source_file_id}"),
            "continuity_version": int(
                source_meta.get(
                    "continuity_version",
                    (continuity_asset or {}).get("version", 1),
                )
                or 1
            ),
            "source_variant_id": str(source_meta.get("variant_id", "") or ""),
            "generation_mode": "refinement",
            "generation_pass": "same_shot_refine",
            "narrative_role": str(source_meta.get("narrative_role", "generic_storyboard_frame") or "generic_storyboard_frame"),
            "shot_goal": str(source_meta.get("shot_goal", "Refine this storyboard shot while preserving continuity.") or "Refine this storyboard shot while preserving continuity."),
            "view_type": str(source_meta.get("view_type", "refinement") or "refinement"),
            "azimuth": int(source_meta.get("azimuth", 0) or 0),
            "elevation": int(source_meta.get("elevation", 0) or 0),
            "framing": str(source_meta.get("framing", "medium") or "medium"),
            "gaze_target": str(source_meta.get("gaze_target", "") or ""),
            "subject_state": str(source_meta.get("subject_state", "") or ""),
            "background_visibility": str(source_meta.get("background_visibility", "") or ""),
            "information_gain": str(source_meta.get("information_gain", "") or ""),
            "must_change_vs_prev": list(source_meta.get("must_change_vs_prev", []) or []),
            "camera_target": {
                "azimuth": int(source_meta.get("azimuth", 0) or 0),
                "elevation": int(source_meta.get("elevation", 0) or 0),
                "framing": str(source_meta.get("framing", "medium") or "medium"),
                "preset_name": str(source_meta.get("view_type", "refinement") or "refinement"),
            },
            "camera_state": _build_camera_state(
                preset_name=str(source_meta.get("view_type", "refinement") or "refinement"),
                view_type=str(source_meta.get("view_type", "refinement") or "refinement"),
                azimuth=int(source_meta.get("azimuth", 0) or 0),
                elevation=int(source_meta.get("elevation", 0) or 0),
                framing=str(source_meta.get("framing", "medium") or "medium"),
            ),
            "is_primary_variant": False,
            "prompt_snapshot": execution_prompt,
            "summary": str(source_meta.get("summary", "") or ""),
        },
        preferred_position=_preferred_position_for_shot_append(
            canvas_data=canvas_data,
            storyboard_id=str(
                source_meta.get("storyboard_id", f"sb_{source_file_id}")
                or f"sb_{source_file_id}"
            ),
            shot_id=source_shot_id,
            source_element=source_element,
        ),
    )

    if mode == "replace":
        refreshed_canvas = await _load_canvas_context(canvas_id)
        refreshed_files = refreshed_canvas.get("files", {}) if isinstance(refreshed_canvas, dict) else {}
        refreshed_elements = refreshed_canvas.get("elements", []) if isinstance(refreshed_canvas, dict) else []
        if isinstance(refreshed_files, dict) and isinstance(refreshed_elements, list):
            new_file_ids = [file_id for file_id in refreshed_files.keys() if file_id not in existing_file_ids]
            if new_file_ids:
                replacement_file_id = new_file_ids[-1]
                replacement_element = None
                source_element_index = None
                replacement_element_index = None
                for index, element in enumerate(refreshed_elements):
                    if not isinstance(element, dict):
                        continue
                    if str(element.get("fileId", "") or "") == source_file_id:
                        source_element_index = index
                    if str(element.get("fileId", "") or "") == replacement_file_id:
                        replacement_element = element
                        replacement_element_index = index

                if source_element_index is not None and replacement_element:
                    source_element = refreshed_elements[source_element_index]
                    if isinstance(source_element, dict):
                        source_element["fileId"] = replacement_file_id
                        source_element["width"] = replacement_element.get("width", source_element.get("width"))
                        source_element["height"] = replacement_element.get("height", source_element.get("height"))
                    if replacement_element_index is not None:
                        refreshed_elements.pop(replacement_element_index)
                    await db_service.save_canvas_data(canvas_id, json.dumps(refreshed_canvas))

    return {
        "role": "assistant",
        "content": (
            "已替换当前镜头并保留 continuity 约束。"
            if mode == "replace"
            else "已为当前镜头生成新的 refinement 候选，并回写到当前 shot 组。"
        ),
    }


async def set_storyboard_primary_variant(
    canvas_id: str,
    file_id: str,
) -> Dict[str, Any]:
    canvas = await db_service.get_canvas_data(canvas_id)
    canvas_data = (canvas or {}).get("data", {}) if isinstance(canvas, dict) else {}
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        raise RuntimeError("Canvas files are unavailable.")

    target_file = files.get(file_id)
    if not isinstance(target_file, dict):
        raise RuntimeError("Selected image file was not found on canvas.")

    target_meta = target_file.get("storyboardMeta")
    if not isinstance(target_meta, dict):
        raise RuntimeError("Selected image is not a storyboard variant.")

    storyboard_id = str(target_meta.get("storyboard_id", "") or "")
    shot_id = str(target_meta.get("shot_id", "") or "")
    if not storyboard_id or not shot_id:
        raise RuntimeError("Selected storyboard image is missing storyboard grouping metadata.")

    updated_count = 0
    for current_file_id, current_file in files.items():
        if not isinstance(current_file, dict):
            continue
        current_meta = current_file.get("storyboardMeta")
        if not isinstance(current_meta, dict):
            continue
        if str(current_meta.get("storyboard_id", "") or "") != storyboard_id:
            continue
        if str(current_meta.get("shot_id", "") or "") != shot_id:
            continue
        next_meta = dict(current_meta)
        next_meta["is_primary_variant"] = current_file_id == file_id
        current_file["storyboardMeta"] = next_meta
        updated_count += 1

    await db_service.save_canvas_data(canvas_id, json.dumps(canvas_data))
    return {
        "storyboard_id": storyboard_id,
        "shot_id": shot_id,
        "variant_id": str(target_meta.get("variant_id", "") or ""),
        "updated_count": updated_count,
    }
