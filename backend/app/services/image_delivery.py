"""Authenticated image previews backed by a disposable server-side cache.

Call only after the route has checked the viewer's permissions. Originals stay
unchanged in storage; exports and AI reference inputs continue using those files.
"""
from __future__ import annotations

import hashlib
import threading
import uuid
from pathlib import Path

from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError

from .storage import Storage
from ..errors import AppError

_LOCKS = [threading.Lock() for _ in range(32)]
_PREVIEW_VERSION = "webp-v1-1600-q85"


def _preview(storage: Storage, key: str, mime: str, original: bool):
    source = storage.materialize(key)
    if source is None:
        raise AppError(404, "image_missing", "Image file is missing.")
    stat = source.stat()
    if original or stat.st_size <= 256 * 1024:
        return source, mime
    fingerprint = hashlib.sha256(
        f"{_PREVIEW_VERSION}:{key}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    ).hexdigest()
    target = storage.local_path(f"private/image-previews/{fingerprint}.webp")
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + "." + uuid.uuid4().hex)
        try:
            with Image.open(source) as image:
                if image.width * image.height > 40_000_000 or getattr(image, "is_animated", False):
                    return source, mime
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                image.save(temp, format="WEBP", quality=85, method=4)
            temp.replace(target)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            return source, mime
        finally:
            temp.unlink(missing_ok=True)
    # Avoid increasing download size for images already efficiently encoded.
    return (target, "image/webp") if target.stat().st_size < stat.st_size else (source, mime)


def image_response(storage: Storage, key: str, mime: str, filename: str,
                   *, original: bool = False, download: bool = False,
                   if_none_match: str = ""):
    lock = _LOCKS[int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % len(_LOCKS)]
    with lock:
        path, content_type = _preview(storage, key, mime, original)
        stat = path.stat()
    etag = '"' + hashlib.sha256(
        f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    ).hexdigest() + '"'
    headers = {
        # Revalidate after authorization on every request, including after logout.
        "Cache-Control": "private, no-cache",
        "Vary": "Cookie, Authorization",
        "ETag": etag,
        "X-Content-Type-Options": "nosniff",
    }
    if any(value.strip().removeprefix("W/") in (etag, "*")
           for value in if_none_match.split(",")):
        return Response(status_code=304, headers=headers)
    if content_type == "image/webp":
        filename = str(Path(filename).with_suffix(".webp"))
    return FileResponse(path, media_type=content_type, filename=filename,
                        content_disposition_type="attachment" if download else "inline", headers=headers,
                        stat_result=stat)
