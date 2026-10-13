"""Download and verify locked official package bytes before npm ci --ignore-scripts.

No extraction, imported package code, lifecycle scripts or registry substitutions.
Keep cache/evidence off-cloud. Retain package licenses when distributing tools.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
from urllib.request import urlopen

root = Path(sys.argv[1]).resolve()
lock = json.loads((root / "package-lock.json").read_text())
records = []
for key, pin in lock["packages"].items():
    if not key:
        continue
    name = key.rsplit("node_modules/", 1)[1]
    metadata = json.load(urlopen(f'https://registry.npmjs.org/{name}/{pin["version"]}'))
    url = pin["resolved"]
    assert url.startswith("https://registry.npmjs.org/")
    assert metadata["dist"]["tarball"] == url
    assert metadata["dist"]["integrity"] == pin["integrity"]
    raw = urlopen(url).read()
    algorithm, digest = pin["integrity"].split("-", 1)
    assert algorithm == "sha512"
    assert base64.b64encode(hashlib.sha512(raw).digest()).decode() == digest
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        package_path = min((m.name for m in archive.getmembers() if m.isfile() and m.name.endswith('/package.json')), key=lambda p: p.count('/'))
        package = json.load(archive.extractfile(package_path))
        licenses = {m.name: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                    for m in archive.getmembers() if m.isfile() and
                    any(x in m.name.rsplit("/", 1)[-1].lower() for x in ("license", "notice", "copying"))}
    assert package["name"] == name and package["version"] == pin["version"]
    license_name = metadata.get("license")
    assert license_name in {"MIT", "ISC", "BSD-3-Clause", "Apache-2.0", "MPL-2.0"}, (name, license_name)
    # Native platform archives may carry their notice in the parent tool package.
    # Record this explicitly for review; these tools are not shipped in the UI.
    repository = metadata.get("repository", {})
    records.append(dict(name=name, version=pin["version"], repository=repository,
                        license=license_name, licenses=licenses, url=url,
                        notice_location="archive" if licenses else "parent tool / upstream source (review required)",
                        integrity=pin["integrity"], sha256=hashlib.sha256(raw).hexdigest()))
    cache = root / "audited-tarballs"
    cache.mkdir(exist_ok=True)
    (cache / (name.replace("/", "_") + "-" + pin["version"] + ".tgz")).write_bytes(raw)
report = dict(lock_sha256=hashlib.sha256((root / "package-lock.json").read_bytes()).hexdigest(), packages=records)
(root / "dependency-audit.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps([dict(name=r["name"], repository=r["repository"], license=r["license"]) for r in records], indent=2))
