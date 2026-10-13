"""New synthetic stores only; pytest's basetemp is off-cloud."""
import sys
from pathlib import Path

# Import roots; a test module that imports LOOPBACK_ORIGIN must not reorder roots already set.
for _root in (Path(__file__).resolve().parents[1] / 'src', Path(__file__).resolve().parents[2] / 'integration/tests'):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

# The one loopback origin of the API tests: sessions, Origin checks and the in-process test
# client all use it. Nothing listens on it, and it is never a port an installation serves on.
LOOPBACK_ORIGIN = 'http://127.0.0.1:19999'
