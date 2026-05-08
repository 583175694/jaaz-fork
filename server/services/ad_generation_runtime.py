from typing import Any, Dict, List, Optional, Tuple

from models.config_model import ModelInfo
from services.ad_prompt_compiler_service import (
    build_fallback_brief,
    compile_image_prompt,
    evaluate_image_prompt,
    rewrite_image_prompt,
)


async def maybe_compile_ad_image_messages(
    messages: List[Dict[str, Any]],
    text_model: ModelInfo,
) -> List[Dict[str, Any]]:
    """Rewrite the latest user text into a more professional advertising image prompt.

    This only touches plain text-first image requests. It intentionally skips
    multimodal editing/reference requests and requests that already contain
    explicit structured image blocks.
    """
    if not messages:
        return messages

    latest = messages[-1]
    if latest.get("role") != "user":
        return messages

    content = latest.get("content")
    prompt, content_mode = _extract_latest_user_prompt(content)
    if not prompt:
        return messages

    lower_prompt = prompt.lower()
    if "<input_images" in lower_prompt or content_mode == "multimodal":
        return messages

    image_intent_signals = [
        "image",
        "images",
        "picture",
        "pictures",
        "shot",
        "shots",
        "storyboard",
        "keyframe",
        "分镜",
        "分镜图",
        "图片",
        "图像",
        "海报",
        "画面",
    ]
    video_only_signals = [
        "video",
        "videos",
        "短片",
        "视频",
        "广告片",
        "片子",
    ]

    has_image_signal = any(signal in lower_prompt for signal in image_intent_signals)
    has_video_signal = any(signal in lower_prompt for signal in video_only_signals)
    if not has_image_signal:
        return messages
    if has_video_signal:
        return messages

    print(
        "🧠 maybe_compile_ad_image_messages using deterministic brief",
        {
            "provider": text_model.get("provider"),
            "model": text_model.get("model"),
            "prompt_preview": prompt[:160],
        },
    )
    brief = build_fallback_brief(
        user_prompt=prompt,
        duration=8,
        aspect_ratio="16:9",
        platform_hint="storyboard image generation",
    )

    compiled_prompt = compile_image_prompt(
        brief=brief,
        original_prompt=prompt,
        aspect_ratio="16:9",
    )
    qa_issues = evaluate_image_prompt(compiled_prompt)
    if qa_issues:
        compiled_prompt = rewrite_image_prompt(compiled_prompt, qa_issues)

    print(
        "🧠 Compiled advertising image prompt",
        {
            "provider": text_model.get("provider"),
            "model": text_model.get("model"),
            "original_preview": prompt[:120],
            "compiled_preview": compiled_prompt[:200],
            "qa_issues": qa_issues,
        },
    )

    updated_messages = list(messages)
    updated_latest = dict(latest)
    updated_latest["content"] = compiled_prompt
    updated_messages[-1] = updated_latest
    return updated_messages


def _extract_latest_user_prompt(content: Any) -> Tuple[str, str]:
    if isinstance(content, str):
        return content.strip(), "text"

    if not isinstance(content, list):
        return "", "unsupported"

    text_parts: List[str] = []
    has_non_text_part = False
    for item in content:
        if not isinstance(item, dict):
            has_non_text_part = True
            continue

        if item.get("type") == "text" and isinstance(item.get("text"), str):
            text_parts.append(item["text"].strip())
        else:
            has_non_text_part = True

    prompt = "\n".join(part for part in text_parts if part).strip()
    if not prompt:
        return "", "unsupported"
    return prompt, "multimodal" if has_non_text_part else "text_list"
