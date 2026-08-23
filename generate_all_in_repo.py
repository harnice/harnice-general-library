"""Run every *_generator.py in the repository."""

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    for path in sorted(ROOT.rglob("*_generator.py")):
        runpy.run_path(str(path), run_name="__main__")
