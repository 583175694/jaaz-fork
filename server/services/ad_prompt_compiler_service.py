import json
import re
from typing import Any, Dict, List, Optional, TypedDict

from langchain_openai import ChatOpenAI

from models.config_model import ModelInfo
from services.config_service import config_service
from utils.http_client import HttpClient


class CreativeBrief(TypedDict, total=False):
    brand_or_product_context: str
    objective: str
    audience: str
    platform: str
    single_minded_message: str
    reason_to_believe: str
    tone: str
    mood_keywords: List[str]
    visual_keywords: List[str]
    product_priority: str
    cta_or_final_impression: str
    duration_seconds: int
    aspect_ratio: str


class VideoPromptCompilation(TypedDict, total=False):
    opening_frame_role: str
    ending_frame_role: str
    transition_style: str
    camera_motion_rules: List[str]
    product_motion_rules: List[str]
    environment_motion_rules: List[str]
    final_packshot_rules: List[str]
    negative_rules: List[str]
    final_prompt: str


DEFAULT_BRIEF: CreativeBrief = {
    "brand_or_product_context": "",
    "objective": "Create a professional advertising clip that communicates the product clearly.",
    "audience": "General consumer audience",
    "platform": "Short-form marketing video",
    "single_minded_message": "The product should feel desirable, premium, and commercially compelling.",
    "reason_to_believe": "Show the product with clear visual hierarchy and premium presentation.",
    "tone": "premium commercial",
    "mood_keywords": ["premium", "polished", "commercial"],
    "visual_keywords": ["hero product", "clean composition", "controlled lighting"],
    "product_priority": "The product remains the visual hero at all times.",
    "cta_or_final_impression": "End with a clear hero packshot.",
    "duration_seconds": 8,
    "aspect_ratio": "16:9",
}


async def ensure_config_initialized() -> None:
    if not getattr(config_service, "initialized", False):
        await config_service.initialize()


def _create_text_model(text_model: ModelInfo) -> ChatOpenAI:
    provider = text_model.get("provider")
    url = text_model.get("url")
    api_key = config_service.app_config.get(provider, {}).get("api_key", "")
    if not provider or not str(provider).strip():
        raise ValueError("Text model provider is missing for prompt compilation")
    if not url or not str(url).strip():
        raise ValueError(f"Text model URL is missing for provider `{provider}`")
    if not api_key or not str(api_key).strip():
        raise ValueError(f"Text model API key is missing for provider `{provider}`")
    http_client = HttpClient.create_sync_client()
    http_async_client = HttpClient.create_async_client()
    return ChatOpenAI(
        model=text_model.get("model"),
        api_key=api_key,  # type: ignore[arg-type]
        timeout=300,
        base_url=url,
        temperature=0,
        http_client=http_client,
        http_async_client=http_async_client,
    )


def _extract_text(response: Any) -> str:
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content).strip()


def _parse_json_response(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _normalize_list(value: Any, fallback: List[str]) -> List[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized
    return fallback


def _contains_meaningful_chinese(text: str) -> bool:
    return len(re.findall(r"[\u4e00-\u9fff]", str(text or ""))) >= 8


def _normalize_brief(data: Dict[str, Any], duration: int, aspect_ratio: str) -> CreativeBrief:
    brief: CreativeBrief = {
        "brand_or_product_context": str(
            data.get("brand_or_product_context") or DEFAULT_BRIEF["brand_or_product_context"]
        ),
        "objective": str(data.get("objective") or DEFAULT_BRIEF["objective"]),
        "audience": str(data.get("audience") or DEFAULT_BRIEF["audience"]),
        "platform": str(data.get("platform") or DEFAULT_BRIEF["platform"]),
        "single_minded_message": str(
            data.get("single_minded_message") or DEFAULT_BRIEF["single_minded_message"]
        ),
        "reason_to_believe": str(
            data.get("reason_to_believe") or DEFAULT_BRIEF["reason_to_believe"]
        ),
        "tone": str(data.get("tone") or DEFAULT_BRIEF["tone"]),
        "mood_keywords": _normalize_list(
            data.get("mood_keywords"), list(DEFAULT_BRIEF["mood_keywords"] or [])
        ),
        "visual_keywords": _normalize_list(
            data.get("visual_keywords"), list(DEFAULT_BRIEF["visual_keywords"] or [])
        ),
        "product_priority": str(
            data.get("product_priority") or DEFAULT_BRIEF["product_priority"]
        ),
        "cta_or_final_impression": str(
            data.get("cta_or_final_impression") or DEFAULT_BRIEF["cta_or_final_impression"]
        ),
        "duration_seconds": int(data.get("duration_seconds") or duration or 8),
        "aspect_ratio": str(data.get("aspect_ratio") or aspect_ratio or "16:9"),
    }
    return brief


def build_fallback_brief(
    user_prompt: str,
    duration: int,
    aspect_ratio: str,
    platform_hint: Optional[str] = None,
) -> CreativeBrief:
    brief = dict(DEFAULT_BRIEF)
    brief["brand_or_product_context"] = user_prompt[:500]
    brief["platform"] = platform_hint or brief["platform"]
    brief["duration_seconds"] = duration
    brief["aspect_ratio"] = aspect_ratio
    return brief


async def compile_creative_brief(
    text_model: ModelInfo,
    user_prompt: str,
    duration: int,
    aspect_ratio: str,
    platform_hint: Optional[str] = None,
) -> CreativeBrief:
    await ensure_config_initialized()
    print(
        "🧠 compile_creative_brief start",
        {
            "provider": text_model.get("provider"),
            "model": text_model.get("model"),
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "platform_hint": platform_hint,
            "prompt_preview": user_prompt[:160],
        },
    )
    prompt = f"""
You are an advertising creative strategist. Convert the user's request into a concise JSON creative brief for image and short-form video generation.

Return valid JSON only with this schema:
{{
  "brand_or_product_context": string,
  "objective": string,
  "audience": string,
  "platform": string,
  "single_minded_message": string,
  "reason_to_believe": string,
  "tone": string,
  "mood_keywords": string[],
  "visual_keywords": string[],
  "product_priority": string,
  "cta_or_final_impression": string,
  "duration_seconds": number,
  "aspect_ratio": string
}}

Rules:
- Focus on professional advertising language, not literary writing.
- Do not invent specific brand assets.
- Use the user's product/brand context if present.
- If the user is vague, make commercially reasonable defaults.
- Keep each field concise but useful for prompt compilation.

User prompt:
{user_prompt}

Runtime constraints:
- duration_seconds: {duration}
- aspect_ratio: {aspect_ratio}
- platform_hint: {platform_hint or "not specified"}
"""
    try:
        llm = _create_text_model(text_model)
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        parsed = _parse_json_response(_extract_text(response))
        brief = _normalize_brief(parsed, duration, aspect_ratio)
        print(
            "🧠 compile_creative_brief done",
            {
                "provider": text_model.get("provider"),
                "model": text_model.get("model"),
                "objective": brief.get("objective"),
                "tone": brief.get("tone"),
                "platform": brief.get("platform"),
            },
        )
        return brief
    except Exception as exc:
        print("⚠️ Creative brief compilation failed, using fallback", {"error": str(exc)})
        return build_fallback_brief(user_prompt, duration, aspect_ratio, platform_hint)


def compile_image_prompt(
    brief: CreativeBrief,
    original_prompt: str,
    aspect_ratio: str,
) -> str:
    mood = ", ".join(brief.get("mood_keywords", []))
    visual = ", ".join(brief.get("visual_keywords", []))
    return (
        f"Create a premium commercial storyboard keyframe for {brief.get('platform', 'short-form advertising')}.\n\n"
        f"Creative objective: {brief.get('objective')}\n"
        f"Audience feeling: {brief.get('audience')}\n"
        f"Single-minded message: {brief.get('single_minded_message')}\n"
        f"Reason to believe: {brief.get('reason_to_believe')}\n"
        f"Tone: {brief.get('tone')}\n"
        f"Product priority: {brief.get('product_priority')}\n"
        f"Visual direction: {visual}\n"
        f"Mood: {mood}\n"
        f"Aspect ratio: {aspect_ratio}\n\n"
        f"Original request context:\n{original_prompt}\n\n"
        "Requirements:\n"
        "- The image must feel like a professionally art-directed advertising still.\n"
        "- Use strong focal hierarchy and clean commercial composition.\n"
        "- Keep the product or main subject visually dominant.\n"
        "- Use controlled lighting, premium material rendering, and restrained clutter.\n"
        "- Make the frame usable as a storyboard keyframe for a marketing video.\n"
        "- Avoid random background noise, cheap CGI feel, awkward anatomy, distorted packaging, and messy layout.\n"
    )


def _fallback_video_compilation(
    brief: CreativeBrief,
    original_prompt: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    selected_image_count: int,
    selection_mode: str = "reference_images",
) -> VideoPromptCompilation:
    if selection_mode == "start_end_frames" and selected_image_count >= 2:
        image_usage_block = (
            "请把所附分镜图作为明确的画面锚点来使用。\n"
            "- 参考图 1 是开场画面的目标状态。\n"
            "- 参考图 2 是结尾画面的目标状态。\n"
            "- 整条视频必须是在同一广告语境下，从图 1 自然过渡到图 2 的连续镜头。\n"
            "- 不要把两张图当成彼此无关的灵感拼贴。\n\n"
        )
        narrative_block = (
            "叙事结构：\n"
            "- 开场：先准确贴合参考图 1 的视觉语言、构图逻辑和情绪状态。\n"
            "- 发展：在保持场景连续的前提下，设计一个清晰的广告动作节点，强化卖点表达。\n"
            "- 收束：最终落到接近参考图 2 的构图状态、叙事状态和产品清晰度。\n\n"
        )
        motion_block = (
            "运动语言：\n"
            "- 镜头必须让人感到是从起始分镜自然推进到结束分镜，而不是硬切换。\n"
            "- 人物身份、服装、发型、妆面、产品外观、环境关系、道具关系和光线逻辑都要保持稳定。\n"
            "- 整体必须是同一个场景、同一个视觉世界，不能突然跳到另一个房间、另一个景别体系或无关背景。\n"
            "- 如果结束画面更紧、更干净，要理解成同一场景内的推进或重构图，而不是切到别处。\n"
            "- 让镜头运动、主体动作、光影变化、反射、氛围或产品操作来承担过渡节奏。\n"
            "- 避免混乱运动、主体漂移、突兀换景和无关的炫技镜头。\n\n"
        )
    else:
        image_usage_block = (
            "请把所附分镜图作为产品形态、画面气质和构图连续性的核心锚点。\n\n"
        )
        narrative_block = (
            "叙事结构：\n"
            "- 开场：用清晰、抓人的视觉钩子和一眼可读的广告构图进入。\n"
            "- 发展：通过克制而明确的镜头运动去展示或强化产品。\n"
            "- 收束：以产品清晰可见、适合营销投放的英雄定格画面结束。\n\n"
        )
        motion_block = (
            "运动语言：\n"
            "- 产品始终保持稳定、可辨识。\n"
            "- 可以用光线、氛围、反射、粒子、液体或环境细节来制造运动感。\n"
            "- 避免杂乱运动，也不要把镜头做成空泛的电影感填充镜头。\n\n"
        )

    final_prompt = (
        f"生成一条 {duration} 秒、{aspect_ratio} 比例、{resolution} 分辨率的高质感商业广告视频。\n\n"
        f"目标：{brief.get('objective')}\n"
        f"受众感受：{brief.get('audience')}\n"
        f"核心表达：{brief.get('single_minded_message')}\n"
        f"整体调性：{brief.get('tone')}\n"
        f"{image_usage_block}"
        f"{narrative_block}"
        "镜头语言：\n"
        "- 使用缓慢、明确、具有高级广告感的镜头运动。\n"
        "- 始终保持清晰的主体层级和产品可见度。\n\n"
        f"{motion_block}"
        "商业规则：\n"
        "- 产品始终是视觉主角。\n"
        "- 除非需求明确要求换景，否则从开场到结尾都保持同一场景身份。\n"
        "- 最终画面必须是干净、明确、可投放的英雄产品定格。\n"
        "- 节奏保持高级、克制、具备广告片感。\n"
        "- 不要出现产品变形、杂乱收尾或气质不符的道具。\n\n"
        f"原始需求上下文：\n{original_prompt}\n"
        f"参考图数量：{selected_image_count}"
    )
    return {
        "opening_frame_role": "opening_hook",
        "ending_frame_role": "hero_packshot",
        "transition_style": "controlled premium reveal",
        "camera_motion_rules": [
            "Use intentional premium advertising camera movement.",
            "Maintain strong focal hierarchy.",
        ],
        "product_motion_rules": [
            "Keep the product stable and recognizable.",
            "Avoid morphing or distortion.",
        ],
        "environment_motion_rules": [
            "Use light, reflections, atmosphere, particles, or liquid for motion.",
        ],
        "final_packshot_rules": [
            "End on a clear hero packshot suitable for marketing usage.",
        ],
        "negative_rules": [
            "No chaotic motion",
            "No messy ending",
            "No cheap CGI feel",
            "No warped packaging",
        ],
        "final_prompt": final_prompt,
    }


async def compile_video_prompt(
    text_model: ModelInfo,
    brief: CreativeBrief,
    original_prompt: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
    selected_image_count: int,
    selection_mode: str = "reference_images",
) -> VideoPromptCompilation:
    await ensure_config_initialized()
    prompt = f"""
You are a professional commercial film prompt director. Convert the user's request and creative brief into a JSON video prompt plan for an advertising generation model.

Return valid JSON only with this schema:
{{
  "opening_frame_role": string,
  "ending_frame_role": string,
  "transition_style": string,
  "camera_motion_rules": string[],
  "product_motion_rules": string[],
  "environment_motion_rules": string[],
  "final_packshot_rules": string[],
  "negative_rules": string[],
  "final_prompt": string
}}

Rules:
- Write for a premium marketing video, not a generic cinematic clip.
- Assume the attached images are storyboard anchors.
- If selection_mode is start_end_frames and there are two images, treat image 1 as the opening frame target and image 2 as the ending frame target.
- The final_prompt must explicitly include opening, development, and hero resolution.
- The final_prompt must end with a strong hero packshot requirement.
- The final_prompt must be written directly in Simplified Chinese. Keep the whole prompt in Chinese except unavoidable brand names or model names.
- Preserve the user's product/brand context without inventing asset details.
- Keep the product recognizable and visually dominant.

Creative brief:
{json.dumps(brief, ensure_ascii=False)}

Original request:
{original_prompt}

Runtime constraints:
- duration: {duration}
- aspect_ratio: {aspect_ratio}
- resolution: {resolution}
- selected_image_count: {selected_image_count}
- selection_mode: {selection_mode}
"""
    try:
        llm = _create_text_model(text_model)
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        parsed = _parse_json_response(_extract_text(response))
        compiled = _fallback_video_compilation(
            brief, original_prompt, duration, aspect_ratio, resolution, selected_image_count, selection_mode
        )
        compiled.update({
            "opening_frame_role": str(parsed.get("opening_frame_role") or compiled["opening_frame_role"]),
            "ending_frame_role": str(parsed.get("ending_frame_role") or compiled["ending_frame_role"]),
            "transition_style": str(parsed.get("transition_style") or compiled["transition_style"]),
            "camera_motion_rules": _normalize_list(
                parsed.get("camera_motion_rules"), compiled["camera_motion_rules"]
            ),
            "product_motion_rules": _normalize_list(
                parsed.get("product_motion_rules"), compiled["product_motion_rules"]
            ),
            "environment_motion_rules": _normalize_list(
                parsed.get("environment_motion_rules"), compiled["environment_motion_rules"]
            ),
            "final_packshot_rules": _normalize_list(
                parsed.get("final_packshot_rules"), compiled["final_packshot_rules"]
            ),
            "negative_rules": _normalize_list(
                parsed.get("negative_rules"), compiled["negative_rules"]
            ),
            "final_prompt": str(parsed.get("final_prompt") or compiled["final_prompt"]),
        })
        compiled["final_prompt"] = await _ensure_video_prompt_in_simplified_chinese(
            text_model=text_model,
            final_prompt=str(compiled.get("final_prompt") or ""),
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        )
        return compiled
    except Exception as exc:
        print("⚠️ Video prompt compilation failed, using fallback", {"error": str(exc)})
        return _fallback_video_compilation(
            brief, original_prompt, duration, aspect_ratio, resolution, selected_image_count, selection_mode
        )


async def _ensure_video_prompt_in_simplified_chinese(
    text_model: ModelInfo,
    final_prompt: str,
    duration: int,
    aspect_ratio: str,
    resolution: str,
) -> str:
    normalized = str(final_prompt or "").strip()
    if not normalized or _contains_meaningful_chinese(normalized):
        return normalized

    translation_prompt = f"""
你是一个商业视频提示词本地化编辑。请把下面这段视频生成提示词完整改写成简体中文，直接输出改写后的中文提示词正文，不要输出解释，不要加引号，不要输出 JSON。

要求：
- 保留原始提示词的结构和约束强度。
- 保留开场、发展、收束、英雄定格等叙事结构。
- 保留广告片语气、镜头语言、连续性要求、产品主导性要求。
- 品牌名、产品名、模型名等必须保留时可以不翻译，其余内容全部改成自然、专业、可直接用于生成的简体中文。
- 输出必须是单段可直接使用的视频提示词。
- 当前运行约束：{duration} 秒，{aspect_ratio}，{resolution}。

原始提示词：
{normalized}
"""
    try:
        llm = _create_text_model(text_model)
        response = await llm.ainvoke([{"role": "user", "content": translation_prompt}])
        translated = _extract_text(response).strip()
        if translated and _contains_meaningful_chinese(translated):
            return translated
    except Exception as exc:
        print("⚠️ Video prompt Chinese normalization failed, keeping original", {"error": str(exc)})

    return normalized


def evaluate_image_prompt(prompt: str) -> List[str]:
    issues: List[str] = []
    required_signals = [
        "commercial",
        "focal hierarchy",
        "product",
        "lighting",
        "storyboard",
    ]
    prompt_lower = prompt.lower()
    for signal in required_signals:
        if signal not in prompt_lower:
            issues.append(f"missing:{signal}")
    return issues


def rewrite_image_prompt(prompt: str, issues: List[str]) -> str:
    if not issues:
        return prompt
    return (
        prompt
        + "\nAdditional commercial quality enforcement:\n"
        + "- Strengthen product hero visibility and focal hierarchy.\n"
        + "- Push the composition closer to a premium storyboard still for marketing usage.\n"
        + "- Use cleaner commercial lighting and stronger material readability.\n"
    )


def evaluate_video_prompt(compilation: VideoPromptCompilation) -> List[str]:
    issues: List[str] = []
    final_prompt = str(compilation.get("final_prompt") or "").lower()
    signal_groups = {
        "opening": ["opening", "开场", "hook"],
        "hero_packshot": ["hero packshot", "packshot", "产品 packshot", "产品居中", "英雄级产品"],
        "product": ["product", "产品", "精华", "瓶身", "主体"],
        "commercial": ["commercial", "广告", "marketing", "品牌", "高端"],
        "resolution": ["resolution", "收束", "结尾", "final", "hero resolution"],
    }
    for key, aliases in signal_groups.items():
        if not any(alias in final_prompt for alias in aliases):
            issues.append(f"missing:{key}")
    return issues


def rewrite_video_prompt(compilation: VideoPromptCompilation, issues: List[str]) -> VideoPromptCompilation:
    if not issues:
        return compilation
    rewritten = dict(compilation)
    rewritten["final_prompt"] = (
        str(compilation.get("final_prompt") or "")
        + "\n\n补充广告约束：\n"
        + "- 强化开场的视觉抓力。\n"
        + "- 在整个运动过程中保持产品主导性和可辨识度。\n"
        + "- 在中段进一步强化卖点表达。\n"
        + "- 结尾必须落到干净、可投放、主体明确的英雄产品定格画面。\n"
    )
    return rewritten
