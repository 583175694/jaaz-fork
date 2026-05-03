#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def summarize_image_result(result: Any) -> dict[str, Any]:
    data = getattr(result, "data", None)
    if not data:
        return {"ok": False, "reason": "no data"}

    first = data[0]
    return {
        "ok": True,
        "has_url": bool(getattr(first, "url", None)),
        "has_b64_json": bool(getattr(first, "b64_json", None)),
        "revised_prompt": getattr(first, "revised_prompt", None),
        "url_prefix": (getattr(first, "url", "") or "")[:160],
        "b64_prefix": (getattr(first, "b64_json", "") or "")[:80],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe whether a provider is compatible with OpenAI image generation/edit APIs."
    )
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. https://host/v1")
    parser.add_argument("--model", required=True, help="Image model name to test")
    parser.add_argument(
        "--image",
        required=True,
        help="Path to a local input image for edit probing",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip images.generate probing",
    )
    parser.add_argument(
        "--skip-edit",
        action="store_true",
        help="Skip images.edit probing",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"input image not found: {image_path}", file=sys.stderr)
        return 2

    client = OpenAI(api_key=args.api_key, base_url=args.base_url)

    final: dict[str, Any] = {
        "base_url": args.base_url,
        "model": args.model,
        "generate": None,
        "edit": None,
    }

    if not args.skip_generate:
        print_section("images.generate")
        try:
            generate_result = client.images.generate(
                model=args.model,
                prompt="A simple red apple on a white table, studio lighting",
                size="1024x1024",
            )
            summary = summarize_image_result(generate_result)
            final["generate"] = {"success": True, "summary": summary}
            print(json.dumps(final["generate"], ensure_ascii=False, indent=2))
        except Exception as exc:
            final["generate"] = {"success": False, "error": str(exc)}
            print(json.dumps(final["generate"], ensure_ascii=False, indent=2))

    if not args.skip_edit:
        print_section("images.edit")
        try:
            with image_path.open("rb") as image_file:
                edit_result = client.images.edit(
                    model=args.model,
                    image=image_file,
                    prompt="Turn this image into a polished anime-style illustration while preserving the original composition and subject placement.",
                )
            summary = summarize_image_result(edit_result)
            final["edit"] = {"success": True, "summary": summary}
            print(json.dumps(final["edit"], ensure_ascii=False, indent=2))
        except Exception as exc:
            final["edit"] = {"success": False, "error": str(exc)}
            print(json.dumps(final["edit"], ensure_ascii=False, indent=2))

    print_section("final")
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
