"""Deployment regression: long-open students keep the chunks their page references."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("publish_frontend", Path(__file__).parents[2] / "scripts/publish_frontend_assets.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def test_publish_retains_old_chunks_and_refuses_hash_collisions(tmp_path):
    source, target = tmp_path / 'build', tmp_path / 'live'
    for folder in (source, target):
        (folder / 'assets').mkdir(parents=True)
    (target / 'index.html').write_text('old entry')
    (target / 'assets/pdf-old.js').write_text('old PDF module')
    (source / 'assets/pdf-new.js').write_text('new PDF module')
    (source / 'index.html').write_text('new entry')
    publisher.publish(source, target)
    assert (target / 'assets/pdf-old.js').read_text() == 'old PDF module'
    assert (target / 'assets/pdf-new.js').read_text() == 'new PDF module'
    assert (target / 'index.html').read_text() == 'new entry'
    (source / 'assets/pdf-new.js').write_text('unexpected collision')
    (source / 'index.html').write_text('unsafe entry')
    with pytest.raises(ValueError, match='collision'):
        publisher.publish(source, target)
    assert (target / 'index.html').read_text() == 'new entry'
