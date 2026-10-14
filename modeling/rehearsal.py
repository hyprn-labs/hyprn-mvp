"""Build a test image of the patched modeling service; never start a service or open a store.

    python3 modeling/rehearsal.py --native-static

The image is built exactly as deployment/modeling_runtime.py builds the owned service: from the
verified WhatsOpt source build, the pinned Ruby base, the
pinned upstream archive read only through the manager's fail-closed upstream resolver (the
verified upstream cache: HYPRN_MVP_UPSTREAM_CACHE, else the installation's upstream.cache, else
below the data root), the ordered patches and the deployment policy. Source acquisition may use
the network; the final modeling stage has no network access. Both builds use
the installation's container engine. The build log and the image record
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
    identity = modeling_runtime.image_identity(image)
    record = dict(image=image, source_image=identity['source_image'],
                  ruby_image=identity['source_build_inputs']['ruby_image'],
                  source_hashes=modeling_runtime.source_hashes(), evidence=str(evidence))
    (evidence / 'image.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return record


if __name__ == '__main__':
    if sys.argv[1:] != ['--native-static']:
        raise SystemExit('usage: python3 modeling/rehearsal.py --native-static')
    build_native_static()
