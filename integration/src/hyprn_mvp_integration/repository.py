"""Request-local bounded reads through AiiDA's public repository interfaces."""

from contextlib import closing
import io


def read_bundle(repository, backend, request):
    """Bound the bulk fetch, then apply the unchanged retained-record validator.

    The evaluator is also part of the pinned worker. Keep this transport
    optimization host-only so historical surrogates retain their exact runtime.
    """
    from hyprn_mvp_app.execution_bundle import MAX_BYTES
    from .results import artifact_json, retained_bundle

    with repository.open('manifest.json', mode='rb') as stream:
        raw_manifest = stream.read(MAX_BYTES + 1)
    manifest = artifact_json(raw_manifest)

    class BufferedRepository:
        def __init__(self):
            self.files = None

        def open(self, path, mode):
            if mode != 'rb':
                raise ValueError('Binary retained read required')
            if path == 'manifest.json':
                return io.BytesIO(raw_manifest)
            # The original reader has now admitted the manifest version, digest
            # and request pin. Bound the complete inventory before bulk fetching.
            if self.files is None:
                self.files = read_files(repository, backend, _file_bounds(manifest))
            return io.BytesIO(self.files[path])

    return retained_bundle(BufferedRepository(), request)


def _file_bounds(manifest):
    from hyprn_mvp_app.execution_bundle import MAX_BYTES, safe_path

    if len(manifest['files']) > 2000:
        raise ValueError('File count exceeded')
    bounds = {}
    total = 0
    for item in manifest['files']:
        path = safe_path(item['path'])
        size = item['size']
        if path in bounds:
            raise ValueError('Duplicate bundle path')
        if type(size) is not int or not 0 <= size <= MAX_BYTES:
            raise ValueError('Invalid artifact size')
        total += size
        if total > MAX_BYTES:
            raise ValueError('Bundle size exceeded')
        bounds[path] = size
    return bounds


def read_files(repository, backend, bounds):
    """Read already admitted paths/sizes in one backend iterator.

    NodeRepository.get_object resolves logical paths. The storage backend's
    iter_object_streams may reorder or omit keys, so identities and completeness
    are checked explicitly. Content hashes remain the retained reader's concern.
    No bytes or lookup results survive this call.
    """
    paths_by_key = {}
    sizes_by_key = {}
    for path, size in bounds.items():
        item = repository.get_object(path)
        if not item.is_file() or not isinstance(item.key, str) or not item.key:
            raise ValueError('Retained repository file required')
        key = item.key
        if key in sizes_by_key and sizes_by_key[key] != size:
            raise ValueError('Retained object size mismatch')
        sizes_by_key[key] = size
        paths_by_key.setdefault(key, []).append(path)
    files = {}
    seen = set()
    with closing(backend.iter_object_streams(sizes_by_key)) as streams:
        for key, stream in streams:
            if key not in sizes_by_key or key in seen:
                raise ValueError('Unexpected retained repository object')
            seen.add(key)
            size = sizes_by_key[key]
            raw = stream.read(size + 1)
            if not isinstance(raw, bytes) or len(raw) != size:
                raise ValueError('Retained object size mismatch')
            for path in paths_by_key[key]:
                files[path] = raw
    if seen != set(sizes_by_key):
        raise FileNotFoundError('Retained repository object missing')
    return files
