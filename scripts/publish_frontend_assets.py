#!/usr/bin/env python3
"""Publish Vite output without deleting chunks used by already-open pages.

Copy all files before atomically replacing index.html. The deployment image
must contain the resulting merged tree so a later container restart also
retains previous hashed chunks. Do not point this at participant storage.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile


def publish(source: Path, target: Path) -> dict[str, str]:
    source, target = source.resolve(), target.resolve()
    if source == target or source in target.parents or target in source.parents or not (source / 'index.html').is_file():
        raise ValueError('Expected a separate built frontend containing index.html')
    paths = [p for p in source.rglob('*') if p.is_file()]
    manifest = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    # Existing content-addressed filenames must never acquire different bytes.
    for p in paths:
        relative = p.relative_to(source)
        if relative.parts[0] == 'assets' and (target / relative).exists():
            if hashlib.sha256((target / relative).read_bytes()).hexdigest() != manifest[str(relative)]:
                raise ValueError(f'Asset filename collision: {relative}')
    target.mkdir(parents=True, exist_ok=True)
    for p in sorted(paths, key=lambda path: path.name == 'index.html'):
        destination = target / p.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix='.publish-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as out, p.open('rb') as incoming:
                shutil.copyfileobj(incoming, out)
            os.chmod(temp_name, 0o644)
            os.replace(temp_name, destination)
        finally:
            Path(temp_name).unlink(missing_ok=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    print(f'Published {len(publish(args.source, args.target))} files; historical chunks retained')
