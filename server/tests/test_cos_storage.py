import importlib


def _load_storage(monkeypatch, configured: bool):
    if configured:
        monkeypatch.setenv("COS_SECRET_ID", "sid")
        monkeypatch.setenv("COS_SECRET_KEY", "skey")
        monkeypatch.setenv("COS_BUCKET", "hello-agent-1256175414")
        monkeypatch.setenv("COS_REGION", "ap-guangzhou")
        monkeypatch.setenv(
            "COS_PUBLIC_BASE_URL",
            "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com",
        )
        monkeypatch.setenv("COS_KEY_PREFIX", "generated")
    else:
        for name in (
            "COS_SECRET_ID",
            "COS_SECRET_KEY",
            "COS_BUCKET",
            "COS_REGION",
            "COS_PUBLIC_BASE_URL",
            "COS_KEY_PREFIX",
        ):
            monkeypatch.delenv(name, raising=False)

    import services.storage_service as storage_service

    importlib.reload(storage_service)
    return storage_service


def test_upload_returns_none_when_cos_is_not_configured(monkeypatch, tmp_path):
    storage_service = _load_storage(monkeypatch, configured=False)
    file_path = tmp_path / "im_test.png"
    file_path.write_bytes(b"png")

    result = storage_service.storage_service.upload_local_file(
        str(file_path),
        "im_test.png",
        content_type="image/png",
    )

    assert result is None


def test_upload_uses_configured_cos_key_and_returns_public_url(monkeypatch, tmp_path):
    storage_service = _load_storage(monkeypatch, configured=True)
    file_path = tmp_path / "im_test.png"
    file_path.write_bytes(b"png")
    calls = []

    class FakeClient:
        def upload_file(self, **kwargs):
            calls.append(kwargs)
            return {"ETag": '"etag"'}

    monkeypatch.setattr(storage_service, "_create_cos_client", lambda _config: FakeClient())

    result = storage_service.storage_service.upload_local_file(
        str(file_path),
        "im_test.png",
        content_type="image/png",
    )

    assert result == (
        "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com/"
        "generated/im_test.png"
    )
    assert calls == [
        {
            "Bucket": "hello-agent-1256175414",
            "Key": "generated/im_test.png",
            "LocalFilePath": str(file_path),
            "EnableMD5": True,
        }
    ]


def test_upload_bytes_uses_configured_cos_key_and_returns_public_url(monkeypatch):
    storage_service = _load_storage(monkeypatch, configured=True)
    calls = []

    class FakeClient:
        def put_object(self, **kwargs):
            calls.append(kwargs)
            return {"ETag": '"etag"'}

    monkeypatch.setattr(storage_service, "_create_cos_client", lambda _config: FakeClient())

    result = storage_service.storage_service.upload_bytes(
        b"png",
        "apipod_video_ref_1.png",
        content_type="image/png",
    )

    assert result == (
        "https://hello-agent-1256175414.cos.ap-guangzhou.myqcloud.com/"
        "generated/apipod_video_ref_1.png"
    )
    assert calls == [
        {
            "Bucket": "hello-agent-1256175414",
            "Key": "generated/apipod_video_ref_1.png",
            "Body": b"png",
            "EnableMD5": True,
            "ContentType": "image/png",
        }
    ]
