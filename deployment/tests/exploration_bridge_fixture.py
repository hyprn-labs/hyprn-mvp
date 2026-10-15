"""Exercise the existing continuous dispatcher in an isolated native scope."""

from pathlib import Path
import sys
import json
import time

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPO / 'deployment'),
    str(REPO / 'application/src'),
    str(REPO / 'integration/src'),
]

import scoped_fixture as guard


def prepare_numerical_runtime(scope):
    """Fresh computation attestation beside, never over, historical originals."""
    from execution_runtime import build_worker
    from hyprn_mvp_integration import launcher

    marker = scope.root / 'artifacts/numerical-runtime.json'
    if marker.exists():
        root = Path(json.loads(marker.read_text())['root'])
        launcher.require_attestation(root=root)
        return root
    fresh = guard.allocate_scope(guard.new_scope())
    build_worker(root=fresh.root)
    assert launcher.attest(root=fresh.root)['passed']
    marker.write_text(json.dumps(dict(root=str(fresh.root))))
    return fresh.root


def main():
    from aiida import load_profile
    from aiida.manage import get_manager
    from hyprn_mvp_integration.calculation import NativeExecution
    import combined_fixture
    import dispatch_runtime

    scope = guard.scope_from_environment()
    load_profile(scope.profile)
    marker = scope.root / 'artifacts/numerical-runtime.json'
    numerical_root = Path(json.loads(marker.read_text())['root']) if marker.exists() else None
    native = NativeExecution(
        backend=get_manager().get_profile_storage(), root=scope.root, numerical_root=numerical_root
    )
    original = dispatch_runtime.native_call

    def measured(native, method, values, **kwargs):
        started = time.monotonic()
        try:
            return original(native, method, values, **kwargs)
        finally:
            print(
                json.dumps(dict(method=method, seconds=time.monotonic() - started)),
                file=sys.stderr,
                flush=True,
            )

    dispatch_runtime.native_call = measured
    status = dispatch_runtime.bridge_child(
        native,
        [guard.APPROVED_CONTRACT_PYTHON, '-B', combined_fixture.__file__, 'dispatch'],
        env=guard.clean_environment(scope),
        cwd=REPO,
        on_ready=lambda: (scope.root / 'artifacts/exploration-bridge-ready.json').write_text('{}'),
    )
    raise SystemExit(status)


if __name__ == '__main__':
    main()
