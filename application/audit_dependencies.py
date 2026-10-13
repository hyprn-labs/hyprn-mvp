"""Inspect downloaded wheels as ZIP data; verify PyPI metadata before installation.

usage: python3 application/audit_dependencies.py <dependency directory>

The dependency directory holds the downloaded wheels in ``wheels/`` and receives the report
in ``evidence/dependency-audit.json``. It is named explicitly and kept off-cloud, outside the
repository; there is no default.
"""
import email
import hashlib
import json
from pathlib import Path
import urllib.request
import sys
import zipfile

if len(sys.argv)!=2:raise SystemExit("usage: audit_dependencies.py <dependency directory>")
ROOT=Path(sys.argv[1]).resolve()
rows=[]
for path in sorted((ROOT/"wheels").glob("*.whl")):
    with zipfile.ZipFile(path) as archive:
        metadata=next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        msg=email.message_from_bytes(archive.read(metadata))
        name,version=msg["Name"],msg["Version"]
        license_files=[n for n in archive.namelist() if any(x in n.upper() for x in ("LICENSE","COPYING"))]
        license_text="\n".join(archive.read(n).decode(errors="replace") for n in license_files if not n.endswith("/"))
    url=f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url,timeout=30) as response: record=json.load(response)
    official=next(item for item in record["urls"] if item["filename"]==path.name)
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    assert official["digests"]["sha256"]==checksum
    assert official["url"].startswith("https://files.pythonhosted.org/")
    rows.append(dict(name=name,version=version,filename=path.name,sha256=checksum,
        registry=url,artifact_url=official["url"],project_urls=record["info"]["project_urls"],
        license_expression=msg.get("License-Expression"),license=record["info"].get("license"),
        classifiers=[c for c in msg.get_all("Classifier",[]) if c.startswith("License")],
        license_files=license_files,license_text_sha256=hashlib.sha256(license_text.encode()).hexdigest(),
        license_excerpt=license_text[:350],requires=msg.get_all("Requires-Dist",[])))
(ROOT/"evidence/dependency-audit.json").write_text(json.dumps(rows,indent=2)+"\n")
for row in rows:
    print(row["name"],row["version"],row["license_expression"] or (row["license"] or "")[:80],row["classifiers"],row["project_urls"])
