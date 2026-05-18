import json
from typing import Any, Dict, List, Optional

from nanoid import generate

from services.db_service import db_service


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def ensure_canvas_production_state(canvas_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(canvas_data, dict):
        canvas_data = {}
    production = canvas_data.get("production")
    if not isinstance(production, dict):
        production = {}
        canvas_data["production"] = production

    if not isinstance(production.get("continuity_assets"), dict):
        production["continuity_assets"] = {}
    if not isinstance(production.get("storyboard_plans"), dict):
        production["storyboard_plans"] = {}
    if not isinstance(production.get("video_briefs"), dict):
        production["video_briefs"] = {}

    current_continuity_id = production.get("current_continuity_id")
    if current_continuity_id is None:
        production["current_continuity_id"] = ""
    current_main_image_file_id = production.get("current_main_image_file_id")
    if current_main_image_file_id is None:
        production["current_main_image_file_id"] = ""
    current_storyboard_id = production.get("current_storyboard_id")
    if current_storyboard_id is None:
        production["current_storyboard_id"] = ""
    current_video_brief_id = production.get("current_video_brief_id")
    if current_video_brief_id is None:
        production["current_video_brief_id"] = ""

    return production


async def load_canvas_data(
    canvas_id: str,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    canvas = await db_service.get_canvas_data(canvas_id, client_id=client_id)
    if not canvas:
        return {"elements": [], "files": {}, "production": {}}
    data = canvas.get("data", {}) if isinstance(canvas, dict) else {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("elements", [])
    data.setdefault("files", {})
    ensure_canvas_production_state(data)
    return data


async def save_canvas_data(
    canvas_id: str,
    canvas_data: Dict[str, Any],
    client_id: Optional[str] = None,
) -> None:
    ensure_canvas_production_state(canvas_data)
    await db_service.save_canvas_data(
        canvas_id,
        json.dumps(canvas_data),
        client_id=client_id,
    )


def build_continuity_asset(
    *,
    main_image_file_id: str,
    anchor: Dict[str, Any],
    continuity_bible: Dict[str, Any],
    prompt: str,
) -> Dict[str, Any]:
    continuity_id = str(continuity_bible.get("continuity_id", "") or f"ct_{generate(size=8)}")
    subject_summary = str(
        anchor.get("subject_summary", anchor.get("subject_summary_zh", "")) or ""
    )
    source_prompt_excerpt = str(anchor.get("source_prompt_excerpt", "") or "")
    environment_identity = anchor.get("environment_identity")
    if not isinstance(environment_identity, dict):
        environment_identity = {}
    lighting_identity = anchor.get("lighting_identity")
    if not isinstance(lighting_identity, dict):
        lighting_identity = {}
    style_identity = anchor.get("style_identity")
    if not isinstance(style_identity, dict):
        style_identity = {}

    created_at = _now_ms()
    return {
        "continuity_id": continuity_id,
        "version": 1,
        "status": "draft",
        "source_main_image_file_id": main_image_file_id,
        "prompt": (
            "请确认这组主图连续性资产。后续分镜、多视角和视频会默认继承这些约束。\n\n"
            f"用户创意补充：{prompt or '基于主图自动扩展分镜'}\n"
            f"主体锚点：{subject_summary or '由主图直接推断'}\n"
            f"来源提示：{source_prompt_excerpt or '无'}"
        ),
        "scene_bible": {
            "scene_type": str(environment_identity.get("scene_type", "inferred_from_main_image") or "inferred_from_main_image"),
            "location_summary_zh": "从主图继承场景与空间关系",
            "location_summary_en": "Inherit scene family and spatial layout from the attached main image.",
            "spatial_layout": ["preserve main scene family", "preserve background structure when possible"],
            "background_anchors": ["same-scene continuity"],
            "prop_anchors": ["preserve visible key props when present"],
            "time_of_day": str(lighting_identity.get("time_of_day", "inherit_from_main_image") or "inherit_from_main_image"),
            "lighting_direction": str(lighting_identity.get("lighting_direction", "inherit_from_main_image") or "inherit_from_main_image"),
            "lighting_quality": str(lighting_identity.get("lighting_style", "inherit_from_main_image") or "inherit_from_main_image"),
            "color_temperature": str(style_identity.get("color_temperature", "inherit_from_main_image") or "inherit_from_main_image"),
            "mood_keywords": ["same-scene", "same-lighting", "same-world-state"],
        },
        "character_bible": {
            "subject_type": str(anchor.get("subject_type", "character_or_product") or "character_or_product"),
            "identity_label": subject_summary or "main_image_subject",
            "face_traits": ["preserve subject identity"],
            "hair_traits": ["preserve hairstyle when visible"],
            "body_traits": ["preserve body silhouette when visible"],
            "wardrobe_traits": ["preserve core wardrobe"],
            "product_traits": ["preserve product shape and appearance"],
            "non_drift_traits": ["same subject", "same wardrobe", "same product appearance"],
            "reference_token_en": "main_image_subject",
        },
        "camera_baseline": {
            "facing_direction": "inherit_from_main_image",
            "base_azimuth": 0,
            "base_elevation": 0,
            "base_framing": "medium",
            "lens_feel": "commercial storyboard still",
            "composition_notes": ["preserve continuity first, vary camera second"],
        },
        "locked_rules": {
            "same_scene_required": True,
            "same_subject_required": True,
            "same_wardrobe_required": True,
            "same_lighting_logic_required": True,
            "background_anchor_locked": True,
            "prop_anchor_locked": False,
        },
        "allowed_variations": {
            "camera_view": True,
            "framing": True,
            "pose": True,
            "expression": True,
            "minor_background_shift": True,
            "scene_change": False,
        },
        "created_at": created_at,
        "updated_at": created_at,
        "main_image_summary": {
            "source_main_image_file_id": main_image_file_id,
            "subject_summary": subject_summary,
            "source_prompt_excerpt": source_prompt_excerpt,
        },
        "continuity_summary": {
            "hard_constraints": list((continuity_bible.get("hard_constraints") or {}).keys()),
            "soft_constraints": continuity_bible.get("soft_constraints"),
            "allowed_variations": continuity_bible.get("allowed_variations"),
        },
    }


def build_storyboard_plan_asset(
    *,
    continuity_asset: Dict[str, Any],
    storyboard_plan: Dict[str, Any],
    prompt: str,
) -> Dict[str, Any]:
    shots = storyboard_plan.get("shots", [])
    normalized_shots: List[Dict[str, Any]] = []
    if isinstance(shots, list):
        for shot in shots:
            if not isinstance(shot, dict):
                continue
            normalized_shots.append(
                {
                    "shot_id": str(shot.get("shot_id", "") or ""),
                    "order_index": int(shot.get("order_index", 0) or 0),
                    "narrative_role": str(shot.get("narrative_role", "") or ""),
                    "shot_goal_zh": str(shot.get("shot_goal", "") or ""),
                    "shot_goal_en": str(
                        shot.get("shot_goal_en", shot.get("shot_goal", "")) or ""
                    ),
                    "framing": str(shot.get("framing", "medium") or "medium"),
                    "gaze_target": str(shot.get("gaze_target", "book") or "book"),
                    "subject_state": str(shot.get("subject_state", "reading") or "reading"),
                    "background_visibility": str(
                        shot.get("background_visibility", "medium") or "medium"
                    ),
                    "information_gain": str(shot.get("information_gain", "") or ""),
                    "must_change_vs_prev": list(shot.get("must_change_vs_prev", []) or []),
                    "inherits_from": "main_image",
                    "locked_constraints": [
                        "same_subject",
                        "same_wardrobe",
                        "same_scene",
                        "same_lighting_logic",
                    ],
                    "allowed_variations": list(shot.get("allowed_views", []) or []),
                    "camera_target": {
                        "azimuth": 0,
                        "elevation": 0,
                        "framing": str(shot.get("framing", "medium") or "medium"),
                        "preset_name": str(shot.get("default_view", "front_three_quarter") or "front_three_quarter"),
                    },
                }
            )

    return {
        "storyboard_id": str(storyboard_plan.get("storyboard_id", "") or f"sb_{generate(size=8)}"),
        "continuity_id": str(continuity_asset.get("continuity_id", "") or ""),
        "continuity_version": int(continuity_asset.get("version", 1) or 1),
        "source_main_image_file_id": str(
            storyboard_plan.get("source_main_image_file_id", continuity_asset.get("source_main_image_file_id", "")) or ""
        ),
        "aspect_ratio": str(storyboard_plan.get("aspect_ratio", "16:9") or "16:9"),
        "mode": str(storyboard_plan.get("mode", "linear_storyboard") or "linear_storyboard"),
        "shot_count": int(storyboard_plan.get("shot_count", len(normalized_shots)) or len(normalized_shots)),
        "variant_count_per_shot": int(storyboard_plan.get("variant_count_per_shot", 3) or 3),
        "prompt": (
            "请确认这组分镜规划。确认后才会正式调用模型生成分镜图。\n\n"
            f"创意补充：{prompt or '基于主图自动扩展分镜'}\n"
            "说明：首轮每镜只生成 1 个 primary 镜头；镜头只允许变化机位、景别、视线和姿态，不允许脱离主图场景连续性。"
        ),
        "shots": normalized_shots,
        "status": "draft",
        "created_at": _now_ms(),
        "updated_at": _now_ms(),
    }


def build_video_brief_asset(
    *,
    continuity_asset: Optional[Dict[str, Any]],
    compiled: Dict[str, Any],
    storyboard_id: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
) -> Dict[str, Any]:
    brief = compiled.get("brief", {}) if isinstance(compiled, dict) else {}
    continuity_id = str((continuity_asset or {}).get("continuity_id", "") or "")
    continuity_version = int((continuity_asset or {}).get("version", 1) or 1)
    brief_id = f"vb_{generate(size=8)}"
    now = _now_ms()
    return {
        "brief_id": brief_id,
        "storyboard_id": storyboard_id,
        "continuity_id": continuity_id,
        "continuity_version": continuity_version,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "prompt": (
            "请确认视频生成摘要。系统会优先继承当前分镜主版本与 continuity 资产。\n\n"
            f"目标：{str(brief.get('objective', '') or '输出一条连续的短视频')}\n"
            f"调性：{str(brief.get('tone', '') or 'premium commercial')}"
        ),
        "display_summary": {
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "objective": str(brief.get("objective", "") or ""),
            "tone": str(brief.get("tone", "") or ""),
        },
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }


async def upsert_continuity_asset(canvas_id: str, continuity_asset: Dict[str, Any], *, set_current: bool = True) -> None:
    canvas_data = await load_canvas_data(canvas_id)
    production = ensure_canvas_production_state(canvas_data)
    continuity_id = str(continuity_asset.get("continuity_id", "") or "")
    if not continuity_id:
        return
    existing = production["continuity_assets"].get(continuity_id)
    next_asset = {
        **(existing if isinstance(existing, dict) else {}),
        **continuity_asset,
        "updated_at": _now_ms(),
    }
    production["continuity_assets"][continuity_id] = next_asset
    if set_current:
        production["current_continuity_id"] = continuity_id
        production["current_main_image_file_id"] = str(
            continuity_asset.get("source_main_image_file_id", "") or ""
        )
    await save_canvas_data(canvas_id, canvas_data)


async def upsert_storyboard_plan(canvas_id: str, storyboard_plan: Dict[str, Any]) -> None:
    canvas_data = await load_canvas_data(canvas_id)
    production = ensure_canvas_production_state(canvas_data)
    storyboard_id = str(storyboard_plan.get("storyboard_id", "") or "")
    if not storyboard_id:
        return
    existing = production["storyboard_plans"].get(storyboard_id)
    next_plan = {
        **(existing if isinstance(existing, dict) else {}),
        **storyboard_plan,
        "updated_at": _now_ms(),
    }
    production["storyboard_plans"][storyboard_id] = next_plan
    production["current_storyboard_id"] = storyboard_id
    await save_canvas_data(canvas_id, canvas_data)


async def upsert_video_brief(canvas_id: str, video_brief: Dict[str, Any]) -> None:
    canvas_data = await load_canvas_data(canvas_id)
    production = ensure_canvas_production_state(canvas_data)
    brief_id = str(video_brief.get("brief_id", "") or "")
    if not brief_id:
        return
    existing = production["video_briefs"].get(brief_id)
    next_brief = {
        **(existing if isinstance(existing, dict) else {}),
        **video_brief,
        "updated_at": _now_ms(),
    }
    production["video_briefs"][brief_id] = next_brief
    production["current_video_brief_id"] = brief_id
    await save_canvas_data(canvas_id, canvas_data)


async def get_current_continuity_asset(
    canvas_id: str,
    client_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    canvas_data = await load_canvas_data(canvas_id, client_id=client_id)
    production = ensure_canvas_production_state(canvas_data)
    continuity_id = str(production.get("current_continuity_id", "") or "")
    if not continuity_id:
        return None
    asset = production.get("continuity_assets", {}).get(continuity_id)
    return asset if isinstance(asset, dict) else None


async def get_current_main_image_file_id(
    canvas_id: str,
    client_id: Optional[str] = None,
) -> str:
    canvas_data = await load_canvas_data(canvas_id, client_id=client_id)
    production = ensure_canvas_production_state(canvas_data)
    return str(production.get("current_main_image_file_id", "") or "")


async def set_current_main_image_file_id(
    canvas_id: str,
    file_id: str,
    client_id: Optional[str] = None,
) -> None:
    canvas_data = await load_canvas_data(canvas_id, client_id=client_id)
    production = ensure_canvas_production_state(canvas_data)
    production["current_main_image_file_id"] = str(file_id or "").strip()
    await save_canvas_data(canvas_id, canvas_data, client_id=client_id)


async def get_storyboard_plan(
    canvas_id: str,
    storyboard_id: str,
    client_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    canvas_data = await load_canvas_data(canvas_id, client_id=client_id)
    production = ensure_canvas_production_state(canvas_data)
    plan = production.get("storyboard_plans", {}).get(storyboard_id)
    return plan if isinstance(plan, dict) else None


async def get_current_storyboard_plan(
    canvas_id: str,
    client_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    canvas_data = await load_canvas_data(canvas_id, client_id=client_id)
    production = ensure_canvas_production_state(canvas_data)
    storyboard_id = str(production.get("current_storyboard_id", "") or "")
    if not storyboard_id:
        return None
    plan = production.get("storyboard_plans", {}).get(storyboard_id)
    return plan if isinstance(plan, dict) else None


async def get_current_video_brief(
    canvas_id: str,
    client_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    canvas_data = await load_canvas_data(canvas_id, client_id=client_id)
    production = ensure_canvas_production_state(canvas_data)
    current_video_brief_id = str(production.get("current_video_brief_id", "") or "")
    video_briefs = production.get("video_briefs", {})
    if not isinstance(video_briefs, dict) or not video_briefs:
        return None
    if current_video_brief_id:
        current_item = video_briefs.get(current_video_brief_id)
        if isinstance(current_item, dict):
            return current_item
    sorted_items = sorted(
        [value for value in video_briefs.values() if isinstance(value, dict)],
        key=lambda item: int(item.get("updated_at", 0) or 0),
        reverse=True,
    )
    return sorted_items[0] if sorted_items else None


def collect_primary_storyboard_variants(canvas_data: Dict[str, Any], storyboard_id: str) -> List[Dict[str, Any]]:
    files = canvas_data.get("files", {}) if isinstance(canvas_data, dict) else {}
    if not isinstance(files, dict):
        return []

    selected: List[Dict[str, Any]] = []
    for file_id, file_info in files.items():
        if not isinstance(file_info, dict):
            continue
        meta = file_info.get("storyboardMeta")
        if not isinstance(meta, dict):
            continue
        if storyboard_id and str(meta.get("storyboard_id", "") or "") != storyboard_id:
            continue
        if not bool(meta.get("is_primary_variant")):
            continue
        selected.append(
            {
                "file_id": file_id,
                "storyboard_meta": meta,
                "generation_meta": file_info.get("generationMeta") if isinstance(file_info.get("generationMeta"), dict) else {},
            }
        )
    selected.sort(
        key=lambda item: (
            str(item["storyboard_meta"].get("shot_id", "") or ""),
            str(item["storyboard_meta"].get("variant_id", "") or ""),
        )
    )
    return selected
