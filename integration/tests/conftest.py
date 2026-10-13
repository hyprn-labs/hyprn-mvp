"""Execution tests use only new, explicitly selected off-cloud runtime stores."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'integration/src'), str(ROOT / 'application/src'), str(ROOT)]
