#!/usr/bin/env python3

import argparse
import json
import sys
import urllib.error
import urllib.request


DEFAULT_MODELS = [
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-preview",
    "veo-3.0-fast-generate-001",
    "veo-3.0-generate-001",
]


def load_local_config(config_path: str) -> dict:
    try:
        import tomllib
    except ModuleNotFoundError:
        print("Python 3.11+ is required for tomllib", file=sys.stderr)
        raise

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def classify_status(status: int, body: str) -> str:
    normalized = body.lower()
    if status == 404 and "publisher model" in normalized:
        return "missing_or_no_access"
    if status == 400:
        return "reachable_but_payload_invalid"
    if 200 <= status < 300:
        return "reachable"
    return "other_error"


def probe_model(base_url: str, api_key: str, model: str) -> dict:
    origin = base_url.rstrip("/")
    if origin.endswith("/v1"):
        origin = origin[: -len("/v1")]

    url = f"{origin}/v1/v1beta/models/{model}:predictLongRunning"
    payload = {
        "instances": [
            {
                "prompt": "probe",
            }
        ],
        "parameters": {
            # Intentionally invalid to avoid starting a real generation task
            # while still distinguishing model availability from model-not-found.
            "durationSeconds": 5,
            "aspectRatio": "16:9",
            "resolution": "720p",
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
    )

    status = 0
    body = ""
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover
        return {
            "model": model,
            "status": None,
            "classification": "transport_error",
            "detail": str(exc),
            "url": url,
        }

    return {
        "model": model,
        "status": status,
        "classification": classify_status(status, body),
        "detail": body[:500],
        "url": url,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Low-cost probe for Zenlayer Veo model availability."
    )
    parser.add_argument(
        "--config",
        default="server/user_data/config.toml",
        help="Path to local AI Studio config.toml",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=DEFAULT_MODELS,
        help="Models to probe",
    )
    args = parser.parse_args()

    config = load_local_config(args.config)
    zenlayer = config.get("zenlayer", {})
    base_url = str(zenlayer.get("url", "")).strip()
    api_key = str(zenlayer.get("api_key", "")).strip()

    if not base_url or not api_key:
        print("Zenlayer url/api_key is missing in config", file=sys.stderr)
        return 2

    results = [probe_model(base_url, api_key, model) for model in args.models]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
