import asyncio
import base64


def _data_url(payload: bytes = b"png") -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def test_apipod_data_url_reference_prefers_cos(monkeypatch):
    from tools.video_providers import apipod_provider

    calls = []

    class FakeStorage:
        def upload_bytes(self, data, filename, content_type=None):
            calls.append((data, filename, content_type))
            return "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com/generated/ref.png"

    monkeypatch.setattr(apipod_provider, "storage_service", FakeStorage())

    result = asyncio.run(
        apipod_provider._prepare_public_reference_images([_data_url()])
    )

    assert result == [
        "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com/generated/ref.png"
    ]
    assert calls == [(b"png", "apipod_video_ref_1.png", "image/png")]


def test_apipod_data_url_reference_falls_back_when_cos_unavailable(monkeypatch):
    from tools.video_providers import apipod_provider

    class FakeStorage:
        def upload_bytes(self, data, filename, content_type=None):
            return None

    async def fake_temporary_upload(data, filename, mime_type):
        return f"https://tmpfiles.org/dl/{filename}"

    monkeypatch.setattr(apipod_provider, "storage_service", FakeStorage())
    monkeypatch.setattr(
        apipod_provider,
        "_upload_reference_bytes_to_temporary_public_url",
        fake_temporary_upload,
    )

    result = asyncio.run(
        apipod_provider._prepare_public_reference_images([_data_url()])
    )

    assert result == ["https://tmpfiles.org/dl/apipod_video_ref_1.png"]


def test_apipod_local_reference_prefers_cos(monkeypatch, tmp_path):
    from tools.video_providers import apipod_provider

    (tmp_path / "local_ref.png").write_bytes(b"png")
    calls = []

    class FakeStorage:
        def upload_local_file(self, local_path, filename, content_type=None):
            calls.append((local_path, filename, content_type))
            return "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com/generated/local_ref.png"

    monkeypatch.setattr(apipod_provider, "FILES_DIR", str(tmp_path))
    monkeypatch.setattr(apipod_provider, "storage_service", FakeStorage())

    result = asyncio.run(
        apipod_provider._prepare_public_reference_images(["local_ref.png"])
    )

    assert result == [
        "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com/generated/local_ref.png"
    ]
    assert calls == [(str(tmp_path / "local_ref.png"), "local_ref.png", "image/png")]
