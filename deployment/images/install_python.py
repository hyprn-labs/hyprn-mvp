"""Install only the reviewed uv and its exact managed CPython inside a build stage."""

import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request


def install(lock_path, destination):
    lock = json.loads(Path(lock_path).read_bytes())
    machine = {'aarch64': 'linux-aarch64', 'x86_64': 'linux-x86_64'}[platform.machine()]
    artifact = lock['uv_archives'][machine]
    with urllib.request.urlopen(lock['uv_download_base'] + artifact['archive']) as response:
        raw = response.read(artifact['size'] + 1)
    if len(raw) != artifact['size'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
        raise ValueError('Reviewed uv archive identity mismatch')
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        member = archive.getmember(artifact['archive'].removesuffix('.tar.gz') + '/uv')
        if not member.isfile():
            raise ValueError('Reviewed uv executable is not a regular file')
        executable = Path(destination) / 'uv'
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(archive.extractfile(member).read())
        executable.chmod(0o755)
    environment = dict(
        os.environ,
        UV_PYTHON_INSTALL_DIR=str(Path(destination) / 'python'),
        UV_PYTHON_INSTALL_MIRROR=lock['cpython_install_mirror'],
        UV_PYTHON_PREFERENCE='only-managed',
        UV_NO_CONFIG='1',
    )
    subprocess.run(
        [str(executable), 'python', 'install', lock['cpython_version']],
        env=environment,
        check=True,
    )
    interpreter = subprocess.check_output(
        [str(executable), 'python', 'find', lock['cpython_version']],
        env=environment,
        text=True,
    ).strip()
    subprocess.run(
        [interpreter, '-m', 'venv', '--without-pip', destination + '/venv'],
        env=environment,
        check=True,
    )
    # The reviewed distribution route excludes Berkeley DB's separate extension (L6).
    for extension in (Path(destination) / 'python').glob('*/lib/python*/lib-dynload/_dbm*.so'):
        extension.unlink()
    # Only the venv's hashed application/runtime distributions are shipped.
    for folder in (Path(destination) / 'python').glob('*/lib/python*/site-packages'):
        for child in folder.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    for folder in (Path(destination) / 'python').glob('*/lib/python*/ensurepip'):
        shutil.rmtree(folder)
    for executable in (Path(destination) / 'python').glob('*/bin/pip*'):
        executable.unlink()


if __name__ == '__main__':
    install(*sys.argv[1:])
