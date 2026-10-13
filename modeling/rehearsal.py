"""Build a test image of the patched modeling service; never start a service or open a store.

    python3 modeling/rehearsal.py --native-static

The image is built exactly as deployment/modeling_runtime.py builds the owned service: from the
reviewed WhatsOpt source image (HYPRN_MVP_MODELING_SOURCE_IMAGE), the pinned Ruby base, the
pinned upstream archive in the verified upstream cache below HYPRN_MVP_DATA_ROOT, the ordered
patches and the deployment policy, with no network access. The build log and the image record
go to a new folder below the scratch root (deployment/local_paths.py); the record is printed as
JSON. Static generation tests take the image id from HYPRN_MVP_NATIVE_STATIC_IMAGE; the reviewed
producer image is pinned in deployment/pins.json (``modeling_producer``).
"""
import json
from pathlib import Path
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'deployment'))
import local_paths  # noqa: E402
import modeling_runtime  # noqa: E402


def build_native_static():
    evidence = Path(tempfile.mkdtemp(prefix='hyprn-mvp-modeling-image-', dir=local_paths.scratch_root()))
    image = modeling_runtime.build(evidence=evidence)
    record = dict(image=image, source_image=modeling_runtime.source_image(), ruby_image=modeling_runtime.RUBY_IMAGE,
                  source_hashes=modeling_runtime.source_hashes(), evidence=str(evidence))
    (evidence / 'image.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return record


if __name__ == '__main__':
    if sys.argv[1:] != ['--native-static']:
        raise SystemExit('usage: python3 modeling/rehearsal.py --native-static')
    build_native_static()
