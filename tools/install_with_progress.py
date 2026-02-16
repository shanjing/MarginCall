"""
Run pip install from requirements.txt with a tqdm progress bar (per-package progress).
Used by setup.sh and setup.ps1. Requires tqdm (pip install tqdm first).
"""
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm


def _parse_requirements(path: Path) -> list[str]:
    """Return list of package specs (skip comments, empty lines, -r/-e)."""
    specs: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        specs.append(line)
    return specs


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    req_path = root / "requirements.txt"
    if not req_path.exists():
        print(f"requirements.txt not found at {req_path}", file=sys.stderr)
        return 1

    specs = _parse_requirements(req_path)
    if not specs:
        return 0

    venv_dir = root / ".venv"
    desc = ".venv found, installing required packages" if venv_dir.is_dir() else "Installing packages"

    failed_stderr: list[str] = []
    for spec in tqdm(specs, desc=desc, unit="pkg"):
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", spec, "-q"],
            capture_output=True,
            text=True,
            cwd=str(root),
        )
        if proc.returncode != 0:
            if proc.stderr:
                failed_stderr.append(f"{spec}\n{proc.stderr}")
            else:
                failed_stderr.append(spec)

    if failed_stderr:
        for msg in failed_stderr:
            print(msg, file=sys.stderr)
        return 1
    print("All required packages are installed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
