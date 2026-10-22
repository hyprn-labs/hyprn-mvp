"""Curated, deterministic HYPRN skill archive; no repository or host files are mounted."""

import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

from hyprn_mvp_app.agent_tools import playbook
from hyprn_mvp_app.assistant.claude import ProviderError

REPO = Path(__file__).resolve().parents[1]
SOURCE = 'docs/agents/scientific-engineering/'
FILES = (
    'SKILL.md',
    'references/behavioral-scenarios.md',
    'references/hyprn-primitives.md',
    'references/joint-exploration.md',
    'references/model-analysis-authoring.md',
    'references/primary-sources.md',
    'references/scientific-acceptance.md',
)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def bundle(root=None):
    """Only reviewed Markdown inputs and generated playbook enter the skill."""
    root = REPO if root is None else root
    inputs, files = {}, {}
    for name in FILES:
        path = root / (SOURCE + name)
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(root.resolve())):
            raise ProviderError('skill_source_invalid')
        raw = path.read_bytes()
        inputs[SOURCE + name] = sha256(raw)
        if name == 'SKILL.md':
            raw = raw.replace(b'../../../application/src/hyprn_mvp_app/agent_tools/playbook.py',
                              b'references/playbook.md').replace(b'../playbook.md',
                                                               b'references/playbook.md')
        files['hyprn/' + name] = raw
    source = root / 'application/src/hyprn_mvp_app/agent_tools/playbook.py'
    if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
        raise ProviderError('skill_source_invalid')
    inputs[str(source.relative_to(root))] = sha256(source.read_bytes())
    files['hyprn/references/playbook.md'] = playbook.render_document().encode()
    manifest = {'schema': 'hyprn-managed-skill/v1', 'inputs': inputs,
                'files': {name: sha256(raw) for name, raw in sorted(files.items())}}
    files['hyprn/manifest.json'] = canonical(manifest) + b'\n'
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, raw)
    raw = output.getvalue()
    return raw, {**manifest, 'sha256': sha256(raw)}


def verify_archive(raw, expected):
    """Compare every downloaded file, rejecting duplicate names and extra content.

    The provider may repackage a ZIP, so archive metadata is not a content identity.
    Never extract untrusted files to disk.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if any(stat.S_ISLNK(item.external_attr >> 16) for item in archive.infolist()):
                raise ValueError()
            names = [item.filename for item in archive.infolist() if not item.is_dir()]
            if len(names) != len(set(names)) or sum(i.file_size for i in archive.infolist()) > 2_000_000:
                raise ValueError()
            files = {name: sha256(archive.read(name)) for name in names}
        expected_files = {**expected['files'],
                          'hyprn/manifest.json': sha256(canonical({
                              key: value for key, value in expected.items() if key != 'sha256'
                          }) + b'\n')}
        if files != expected_files:
            raise ValueError()
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, RuntimeError):
        raise ProviderError('provider_skill_drift') from None
