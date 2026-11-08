"""Private JD Cloud objects, accessed by the server through the S3 API."""
from __future__ import annotations

import hashlib
from functools import cached_property
from pathlib import Path
from urllib.parse import quote, urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi.responses import StreamingResponse

from ..config import Settings
from ..errors import AppError


class JdcloudOSS:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def client(self):
        endpoint = self.settings.oss_endpoint_url or ""
        parsed = urlsplit(endpoint)
        if not (
            parsed.scheme == "https" and parsed.hostname
            and not parsed.username and not parsed.password
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
            and self.settings.oss_region and self.settings.oss_bucket
            and self.settings.oss_access_key_id and self.settings.oss_secret_access_key
        ):
            raise AppError(503, "storage_not_configured", "Private OSS storage is not configured.")
        return boto3.session.Session().client(
            "s3", endpoint_url=endpoint.rstrip("/"), region_name=self.settings.oss_region,
            aws_access_key_id=self.settings.oss_access_key_id,
            aws_secret_access_key=self.settings.oss_secret_access_key,
            config=Config(
                signature_version="s3v4", s3={"addressing_style": "virtual"},
                connect_timeout=5, read_timeout=30,
                retries={"mode": "standard", "total_max_attempts": 2},
            ),
        )

    def _call(self, operation: str, **kwargs):
        try:
            return getattr(self.client, operation)(Bucket=self.settings.oss_bucket, **kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise AppError(404, "file_not_found", "File not found.") from None
            # Provider messages can contain request/signature details; keep them private.
            raise AppError(503, "storage_unavailable", "Private OSS storage is temporarily unavailable.") from None
        except BotoCoreError:
            raise AppError(503, "storage_unavailable", "Private OSS storage is temporarily unavailable.") from None

    def _check_new_key(self, key: str, overwrite: bool):
        # Application writes use UUID/content-addressed keys. Guard accidental reuse.
        if overwrite:
            return
        try:
            self._call("head_object", Key=key)
        except AppError as exc:
            if exc.status_code == 404:
                return
            raise
        raise AppError(409, "file_already_exists", "The stored file already exists.")

    def put_bytes(self, key: str, body: bytes, mime: str, *, overwrite=False):
        self._check_new_key(key, overwrite)
        self._call("put_object", Key=key, Body=body, ContentType=mime,
                   Metadata={"sha256": hashlib.sha256(body).hexdigest()})
        return key

    def put_file(self, key: str, path: Path, mime: str, *, overwrite=False):
        self._check_new_key(key, overwrite)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            handle.seek(0)
            self._call("put_object", Key=key, Body=handle, ContentType=mime,
                       ContentLength=path.stat().st_size, Metadata={"sha256": digest.hexdigest()})
        return key

    def read_bytes(self, key: str, maximum: int):
        result = self._call("get_object", Key=key)
        body = result["Body"]
        try:
            if result.get("ContentLength", 0) > maximum:
                raise AppError(413, "file_too_large", "File exceeds the permitted size.")
            data = body.read(maximum + 1)
            if len(data) > maximum:
                raise AppError(413, "file_too_large", "File exceeds the permitted size.")
            return data
        except BotoCoreError:
            raise AppError(503, "storage_unavailable", "Private OSS storage is temporarily unavailable.") from None
        finally:
            body.close()

    def download_to(self, key: str, target: Path):
        result = self._call("get_object", Key=key)
        body = result["Body"]
        try:
            with target.open("wb") as handle:
                for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                    handle.write(chunk)
        except BotoCoreError:
            raise AppError(503, "storage_unavailable", "Private OSS storage is temporarily unavailable.") from None
        finally:
            body.close()

    def response(self, key: str, mime: str, filename: str, *, download=False):
        result = self._call("get_object", Key=key)
        body = result["Body"]

        def chunks():
            try:
                yield from body.iter_chunks(chunk_size=256 * 1024)
            finally:
                body.close()

        disposition = "attachment" if download else "inline"
        headers = {
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename, safe='')}",
        }
        if "ContentLength" in result:
            headers["Content-Length"] = str(result["ContentLength"])
        # Keep the existing authenticated /api/files URL and browser CSP intact.
        return StreamingResponse(chunks(), media_type=mime, headers=headers)
