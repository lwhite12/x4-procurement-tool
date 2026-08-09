"""Shared pytest setup.

The pipeline modules live in src/ as standalone scripts, not an installed
package, so this puts src/ on sys.path for every test module to import from
directly (e.g. `from generate_ships_table import resolve_text`).

Fixtures (sample XML fragments, a temp sqlite db, etc.) will be added here
once the stub tests below start getting implemented.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
