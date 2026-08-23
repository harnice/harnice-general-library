"""Regenerate the library and fail if it differs from the tree being merged."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    subprocess.run(
        [sys.executable, str(ROOT / "generate_all_in_repo.py")],
        cwd=ROOT,
        check=True,
    )
    diff = subprocess.run(["git", "diff", "--exit-code"], cwd=ROOT)
    extra = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if extra.stdout.strip():
        print("Untracked files after generate:")
        print(extra.stdout, end="")
    if diff.returncode != 0 or extra.stdout.strip():
        print(
            "\nGenerated tree does not match what is being merged. "
            "Run `python generate_all_in_repo.py` and commit the result."
        )
        return 1
    print("Generated tree matches the commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
