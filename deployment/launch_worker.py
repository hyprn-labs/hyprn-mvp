"""Trusted CalcJob executable; never imports the candidate file."""
import json
from pathlib import Path
import sys
from manage import isolated, require_attestation

require_attestation()
path = Path(sys.argv[1])
if path.is_symlink() or path.stat().st_size > 65536:
    raise RuntimeError('Source bundle is not a bounded regular file')
result = isolated(path.read_text())
print(json.dumps(result))
sys.exit(0 if result['exit_code'] == 0 else 1)
