from __future__ import annotations

import asyncio
import io
import runpy
import shutil
import zipfile
from pathlib import Path

import httpx
import pytest
from PIL import Image
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.config import Settings
from app.errors import AppError
from app.services.jdcloud_oss import JdcloudOSS
from app.services.storage import Storage
from app.services.image_delivery import image_response
from tests.conftest import complete_k0, demo_image, enter_t1, login_student, save_t1_work


class MemoryS3:
    """Exercise the storage contract without making any billable AI/S3 calls."""
    def __init__(self):
        self.objects = {}

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"ContentLength": len(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        assert "ACL" not in kwargs
        self.objects[Key] = Body if isinstance(Body, bytes) else Body.read()
        return {}

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        data = self.objects[Key]
        return {"ContentLength": len(data), "Body": StreamingBody(io.BytesIO(data), len(data))}


@pytest.fixture
def oss_settings(tmp_path):
    return Settings(_env_file=None, data_dir=tmp_path, storage_backend="jdcloud_oss",
                    oss_endpoint_url="https://s3.cn-south-1.jdcloud-oss.com",
                    oss_region="cn-south-1", oss_bucket="test-private-bucket",
                    oss_access_key_id="test-access", oss_secret_access_key="test-secret")


def test_sdk_uses_explicit_credentials_and_translates_private_errors(oss_settings):
    adapter = JdcloudOSS(oss_settings)
    assert adapter.client.meta.config.signature_version == "s3v4"
    assert adapter.client.meta.config.s3["addressing_style"] == "virtual"
    with Stubber(adapter.client) as stub:
        stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404,
                              expected_params={"Bucket": "test-private-bucket", "Key": "missing.png"})
        stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403,
                              service_message="sensitive upstream details",
                              expected_params={"Bucket": "test-private-bucket", "Key": "denied.png"})
        with pytest.raises(AppError) as missing:
            adapter.read_bytes("missing.png", 100)
        assert missing.value.status_code == 404
        with pytest.raises(AppError) as denied:
            adapter.read_bytes("denied.png", 100)
        assert denied.value.status_code == 503
        assert "sensitive" not in str(denied.value)
        stub.assert_no_pending_responses()


def test_cold_cache_roundtrip_limits_and_conflicting_writes(oss_settings, monkeypatch):
    remote = MemoryS3()
    monkeypatch.setattr(JdcloudOSS, "client", property(lambda self: remote))
    storage = Storage(oss_settings)
    storage.put_bytes("artifacts/new.png", b"source-image", "image/png")
    assert not storage.local_path("artifacts/new.png").exists()
    assert storage.materialize("artifacts/new.png").read_bytes() == b"source-image"
    with pytest.raises(AppError) as large:
        storage.read_bytes("artifacts/new.png", maximum=2)
    assert large.value.status_code == 413
    with pytest.raises(AppError) as conflict:
        storage.put_bytes("artifacts/new.png", b"replacement", "image/png")
    assert conflict.value.status_code == 409
    assert remote.objects["artifacts/new.png"] == b"source-image"
    storage.put_bytes("system/readiness.txt", b"heritage-beta-storage-v1", "text/plain")
    assert storage.ready()


def test_optimized_preview_cache_and_original_preservation(oss_settings, monkeypatch):
    remote = MemoryS3()
    monkeypatch.setattr(JdcloudOSS, "client", property(lambda self: remote))
    image = Image.effect_noise((1800, 1200), 60).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    original = buffer.getvalue()
    key = "keyframes/large.png"
    remote.objects[key] = original
    storage = Storage(oss_settings)
    response = image_response(storage, key, "image/png", "preview.png")
    assert response.media_type == "image/webp"
    assert Path(response.path).stat().st_size < len(original)
    with Image.open(response.path) as preview:
        assert preview.size == (1600, 1067)
    assert storage.local_path(key).read_bytes() == remote.objects[key] == original
    # Repeat visits work from the local cache even if OSS is unavailable.
    remote.objects.clear()
    cached = image_response(storage, key, "image/png", "preview.png",
                            if_none_match=response.headers["etag"])
    assert cached.status_code == 304
    assert cached.headers["cache-control"] == "private, no-cache"
    assert "Cookie" in cached.headers["vary"]
    full = image_response(storage, key, "image/png", "preview.png", original=True,
                          if_none_match=response.headers["etag"])
    assert full.status_code == 200 and full.media_type == "image/png"
    assert Path(full.path).read_bytes() == original


async def test_oss_upload_generation_private_routes_and_export(app_client, monkeypatch):
    client, app, settings = app_client
    remote = MemoryS3()
    monkeypatch.setattr(JdcloudOSS, "client", property(lambda self: remote))
    # Simulate the real migration, then remove local images to prove cloud reads.
    for path in settings.artifacts_dir.rglob("*"):
        if path.is_file():
            remote.objects[str(path.relative_to(settings.data_dir))] = path.read_bytes()
    shutil.rmtree(settings.artifacts_dir)
    settings.storage_backend = "jdcloud_oss"
    remote.objects["system/readiness.txt"] = b"heritage-beta-storage-v1"
    assert (await client.get("/api/health/ready")).status_code == 200
    assert (await client.post("/api/admin/login", json={"password": settings.admin_password})).status_code == 200
    runtime = (await client.get("/api/admin/runtime")).json()
    assert runtime["direct_upload"] is False
    response = await client.post("/api/admin/artifacts/X/versions", data={
        "title": "OSS upload test", "introduction": "Private artifact", "facts_json": "[]",
        "evidence_json": "[]", "uncertainty_json": "[]",
    }, files={"image": ("test.png", demo_image(), "image/png")})
    assert response.status_code == 200, response.text
    image_url = response.json()["artifact"]["image_url"]
    image = await client.get(image_url)
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    assert "location" not in image.headers
    etag = image.headers["etag"]
    cached = await client.get(image_url, headers={"If-None-Match": etag})
    assert cached.status_code == 304 and not cached.content
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as anonymous:
        assert (await anonymous.get(image_url, headers={"If-None-Match": etag})).status_code == 401
    await login_student(client, settings)
    await complete_k0(client)
    await enter_t1(client)
    await save_t1_work(client)
    response = await client.post("/api/student/rounds/1/image-jobs", json={})
    assert response.status_code == 200, response.text
    job_id = response.json()["job"]["id"]
    for _ in range(100):
        job = (await client.get(f"/api/student/image-jobs/{job_id}")).json()["job"]
        if job["status"] in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.05)
    assert job["status"] == "succeeded", job
    assert any(job_id in key for key in remote.objects)
    shutil.rmtree(settings.keyframes_dir)
    image = await client.get(f"/api/files/keyframes/{job_id}")
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    etag = image.headers["etag"]
    original = await client.get(f"/api/files/keyframes/{job_id}?variant=original&download=1")
    assert original.status_code == 200 and original.content == image.content
    assert original.headers["content-disposition"].startswith("attachment;")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as other:
        await login_student(other, settings, class_id=2)
        assert (await other.get(f"/api/files/keyframes/{job_id}", headers={"If-None-Match": etag})).status_code == 404
    exported = await client.get("/api/admin/export")
    assert exported.status_code == 200, exported.text[:200]
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert archive.testzip() is None
        assert any(job_id in name and name.endswith(".png") for name in archive.namelist())


async def test_blob_image_routes_keep_signed_redirects(app_client, monkeypatch):
    from fastapi.responses import RedirectResponse
    from app.models import ArtifactVersion
    from sqlalchemy import select

    client, app, settings = app_client
    await client.post("/api/admin/login", json={"password": settings.admin_password})
    async with app.state.db.session_factory() as session:
        version = (await session.execute(select(ArtifactVersion).limit(1))).scalar_one()
        image_url = f"/api/files/artifacts/{version.id}/image"
    settings.storage_backend = "blob"
    called = []

    def response(self, key, mime, filename, *, download=False):
        called.append(key)
        return RedirectResponse("https://example.invalid/private-signed", status_code=307)

    def materialize(self, key):
        raise AssertionError("Blob images must not be downloaded into the function cache")

    monkeypatch.setattr(Storage, "response", response)
    monkeypatch.setattr(Storage, "materialize", materialize)
    result = await client.get(image_url, follow_redirects=False)
    assert result.status_code == 307 and len(called) == 1
    assert result.headers["location"] == "https://example.invalid/private-signed"


def test_migration_verifies_existing_objects_and_aborts_on_conflict(oss_settings, monkeypatch):
    remote = MemoryS3()
    monkeypatch.setattr(JdcloudOSS, "client", property(lambda self: remote))
    root = oss_settings.data_dir
    (root / "artifacts").mkdir()
    (root / "artifacts" / "one.png").write_bytes(b"original")
    (root / "private").mkdir()
    (root / "private" / "secret.txt").write_bytes(b"must-not-upload")
    migrate = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts" / "migrate_jdcloud_oss.py"))["migrate"]
    preview = migrate(oss_settings, apply=False)
    assert preview["files"] == 1 and not remote.objects
    first = migrate(oss_settings, apply=True)
    assert first["uploaded"] == first["verified"] == 1
    assert not any(key.startswith("private/") for key in remote.objects)
    again = migrate(oss_settings, apply=True)
    assert again["uploaded"] == 0 and again["verified"] == 1
    remote.objects["artifacts/one.png"] = b"conflicting"
    with pytest.raises(RuntimeError, match="mismatch"):
        migrate(oss_settings, apply=True)
    assert remote.objects["artifacts/one.png"] == b"conflicting"
    assert (root / "artifacts" / "one.png").read_bytes() == b"original"
