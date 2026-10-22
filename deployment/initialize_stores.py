"""Explicit initialization of empty development stores from pinned source builds.

This is not a reset command. Both stores and all deployment resource names must be
unused before setup begins. Failures retain their stores and evidence for diagnosis.
"""
import argparse
import json

import application_runtime as app
import local_paths
import modeling_runtime as model

STORES = None if app.ROOT is None or model.DEFAULT_ROOT is None else (app.ROOT, model.DEFAULT_ROOT)
EVIDENCE = None if app.ROOT is None else app.ROOT / 'evidence' / 'initialization'


def emit(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def guarded_empty_root(path):
    if path not in (STORES or ()) or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Exact nonsymlink store required')
    if path.exists() and any(path.iterdir()):
        raise ValueError('Store already has contents; refuse reset, inspect checkpoint')


def bootstrap():
    local_paths.port()
    local_paths.require(STORES)
    for root in STORES:
        guarded_empty_root(root)
    # Refuse collisions before either setup creates files, networks or containers.
    for name, kind in ((model.CONTAINER, None), (app.NAME, None),
                       (model.NETWORK, 'network'), (app.PUBLIC_NETWORK, 'network')):
        info = model.inspect(name) if kind is None else model.inspect(name, kind)
        if info is not None:
            raise ValueError('Existing deployment resource; preserve it and inspect its identity')
    modeling = model.setup(model.DEFAULT_ROOT)
    application = app.setup()
    EVIDENCE.mkdir(mode=0o700)
    emit(EVIDENCE / 'bootstrap.json', dict(application=application, modeling=modeling))
    print('Fresh application/modeling stores provisioned; native environment and attestation pending.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['bootstrap'])
    parser.parse_args()
    bootstrap()
