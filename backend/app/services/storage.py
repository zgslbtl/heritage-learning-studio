"""Private persistent objects with the same relative keys as the local runtime.

Blob control API v12 and signed URL canonicalization follow @vercel/blob's
public protocol. Only object-scoped, short-lived signatures leave the server.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode

import httpx
from fastapi.responses import FileResponse, RedirectResponse

from ..config import Settings
from ..errors import AppError

BLOB_API = "https://vercel.com/api/blob"
UPLOAD_TYPES = ["image/jpeg", "image/png", "image/webp"]


def safe_key(key: str) -> str:
    if not key or key.startswith("/") or "\\" in key or ":" in key or any(
        part in (".", "..", "") for part in key.split("/")
    ) or any(ord(char) < 32 for char in key):
        raise AppError(404, "file_not_found", "File not found.")
    return str(PurePosixPath(key))


def presigned_url(material: dict, key: str, operation: str, store_id: str) -> str:
    """Constrained GET/PUT subset of the official SDK's signing protocol."""
    key = safe_key(key)
    parameters = {} if operation == "get" else {
        "vercel-blob-add-random-suffix": "false",
        "vercel-blob-allow-overwrite": "false",
    }
    lines = [f"operation={operation}", f"pathname={key}"]
    lines.extend(f"{name}={value}" for name, value in parameters.items())
    canonical = "\n".join(sorted(lines, key=lambda value: value.encode("utf-8")))
    signature = base64.urlsafe_b64encode(hmac.new(
        material["clientSigningToken"].encode(), canonical.encode(), hashlib.sha256,
    ).digest()).decode().rstrip("=")
    parameters.update({"vercel-blob-delegation": material["delegationToken"],
                       "vercel-blob-signature": signature})
    if operation == "get":
        base = f"https://{store_id.removeprefix('store_').lower()}.private.blob.vercel-storage.com/{quote(key, safe='/')}"
    elif operation == "put":
        base = f"{BLOB_API}/?{urlencode({'pathname': key})}"
    else:
        raise ValueError("Only scoped reads and uploads are supported")
    return base + ("&" if "?" in base else "?") + urlencode(parameters)


class Storage:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def cloud(self):
        return self.settings.storage_backend == "blob"

    def _credentials(self):
        token = self.settings.blob_read_write_token or os.getenv("BLOB_READ_WRITE_TOKEN")
        if not token or not token.startswith("vercel_blob_rw_"):
            raise AppError(503, "storage_not_configured", "Private storage is not configured.")
        store_id = token[len("vercel_blob_rw_"):].split("_", 1)[0]
        return token, store_id

    def _headers(self):
        token, _ = self._credentials()
        return {"Authorization": f"Bearer {token}", "x-api-version": "12"}

    def local_path(self, key: str):
        key = safe_key(key)
        root = self.settings.data_dir.resolve()
        target = (root / key).resolve()
        if not target.is_relative_to(root):
            raise AppError(404, "file_not_found", "File not found.")
        return target

    def _checked(self, response):
        if response.status_code == 404:
            raise AppError(404, "file_not_found", "File not found.")
        if not response.is_success:
            raise AppError(503, "storage_unavailable", "Private storage is temporarily unavailable.")
        return response

    def put_bytes(self, key: str, body: bytes, mime: str, *, overwrite=False):
        key = safe_key(key)
        if self.cloud:
            with httpx.Client(timeout=60) as client:
                result = self._checked(client.put(BLOB_API + "/", params={"pathname": key},
                    content=body, headers={**self._headers(), "x-vercel-blob-access": "private",
                    "x-content-type": mime, "x-add-random-suffix": "0",
                    "x-allow-overwrite": "1" if overwrite else "0"}))
                if result.json().get("pathname") != key:
                    raise AppError(503, "storage_path_mismatch", "Storage returned an unexpected object.")
        else:
            path = self.local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + ".upload")
            temp.write_bytes(body)
            temp.replace(path)
        return key

    def put_file(self, key: str, path: Path, mime: str, *, overwrite=False):
        if not self.cloud:
            return self.put_bytes(key, path.read_bytes(), mime, overwrite=overwrite)
        key = safe_key(key)
        with path.open("rb") as handle, httpx.Client(timeout=120) as client:
            self._checked(client.put(BLOB_API + "/", params={"pathname": key}, content=handle,
                headers={**self._headers(), "x-vercel-blob-access": "private", "x-content-type": mime,
                         "Content-Length": str(path.stat().st_size), "x-add-random-suffix": "0",
                         "x-allow-overwrite": "1" if overwrite else "0"}))
        return key

    def read_bytes(self, key: str, maximum=32 * 1024 * 1024):
        key = safe_key(key)
        if not self.cloud:
            path = self.local_path(key)
            if not path.is_file():
                raise AppError(404, "file_not_found", "File not found.")
            if path.stat().st_size > maximum:
                raise AppError(413, "file_too_large", "File exceeds the permitted size.")
            return path.read_bytes()
        _, store_id = self._credentials()
        url = f"https://{store_id.lower()}.private.blob.vercel-storage.com/{quote(key, safe='/')}"
        with httpx.Client(timeout=60) as client, client.stream("GET", url, headers=self._headers()) as response:
            self._checked(response)
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > maximum:
                    raise AppError(413, "file_too_large", "File exceeds the permitted size.")
            return bytes(data)

    def materialize(self, key: str):
        path = self.local_path(key)
        if not path.is_file() and self.cloud:
            data = self.read_bytes(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            # UUID temporary names avoid concurrent writers corrupting cached files.
            import uuid
            temp = path.with_name(path.name + "." + uuid.uuid4().hex)
            temp.write_bytes(data)
            temp.replace(path)
        return path if path.is_file() else None

    def signed(self, key: str, operation="get", *, maximum=None, mime=None):
        key = safe_key(key)
        _, store_id = self._credentials()
        payload = {"pathname": key, "operations": [operation], "validUntil": int((time.time() + 60) * 1000)}
        if maximum is not None:
            payload["maximumSizeInBytes"] = maximum
        if mime is not None:
            if mime not in UPLOAD_TYPES:
                raise AppError(422, "invalid_image_type", "Use a PNG, JPEG or WebP image.")
            payload["allowedContentTypes"] = [mime]
        with httpx.Client(timeout=20) as client:
            material = self._checked(client.post(BLOB_API + "/signed-token", json=payload,
                                                headers=self._headers())).json()
        return presigned_url(material, key, operation, store_id)

    def response(self, key: str, mime: str, filename: str, *, download=False):
        if self.cloud:
            return RedirectResponse(self.signed(key), status_code=307,
                                    headers={"Cache-Control": "private, no-store"})
        path = self.materialize(key)
        if path is None:
            raise AppError(404, "file_not_found", "File not found.")
        return FileResponse(path, media_type=mime, filename=filename,
            content_disposition_type="attachment" if download else "inline",
            headers={"Cache-Control": "private, no-store"})

    def ready(self):
        if self.cloud:
            try:
                return self.read_bytes("system/readiness.txt", maximum=256) == b"heritage-beta-storage-v1"
            except (AppError, httpx.HTTPError):
                return False
        try:
            self.settings.ensure_directories()
            return self.settings.data_dir.is_dir()
        except OSError:
            return False
