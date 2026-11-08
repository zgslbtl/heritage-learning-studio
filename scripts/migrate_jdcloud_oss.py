"""Copy persistent files to private OSS without changing keys or deleting local data.

Run with the API image's environment and /data volume; --apply uploads files.
Existing keys must match byte-for-byte. A conflicting remote object aborts migration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import Settings
from app.errors import AppError
from app.services.storage import Storage, safe_key


def migrate(settings: Settings, *, apply: bool):
    storage = Storage(settings.model_copy(update={"storage_backend": "jdcloud_oss"}))
    root = settings.data_dir.resolve()
    records = []
    uploaded = verified = total_bytes = 0
    for directory in ("artifacts", "keyframes", "uploads", "provider-results", "exports"):
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or path.name.startswith(".") or path.suffix in (".tmp", ".upload"):
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RuntimeError("Refusing a symlink outside the data directory")
            key = safe_key(str(path.relative_to(root)))
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if apply:
                try:
                    remote = storage.read_bytes(key, maximum=max(len(data) + 1, 256))
                except AppError as exc:
                    if exc.status_code != 404:
                        raise
                    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    storage.put_file(key, path, mime)
                    uploaded += 1
                    remote = storage.read_bytes(key, maximum=max(len(data) + 1, 256))
                if hashlib.sha256(remote).hexdigest() != digest:
                    raise RuntimeError(f"Remote content mismatch; no overwrite performed: {key}")
                verified += 1
            total_bytes += len(data)
            records.append({"key": key, "bytes": len(data), "sha256": digest})
            print(json.dumps({"file": key, "verified": apply}), flush=True)
    if apply:
        storage.put_bytes("system/readiness.txt", b"heritage-beta-storage-v1", "text/plain", overwrite=True)
        if not storage.ready():
            raise RuntimeError("OSS readiness marker verification failed")
    return {"apply": apply, "files": len(records), "uploaded": uploaded,
            "verified": verified, "bytes": total_bytes, "objects": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = migrate(Settings(), apply=args.apply)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        args.report.chmod(0o600)
    print(json.dumps({k: v for k, v in report.items() if k != "objects"}, ensure_ascii=False))
