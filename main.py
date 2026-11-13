"""MARS SURVIVE 360 launcher.

    python main.py            -> Streamlit UI  (http://localhost:8501)
    python main.py api        -> FastAPI REST  (http://localhost:8601/docs)
    python main.py check      -> system check
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "ui"
    port = argv[2] if len(argv) > 2 else None
    if cmd == "ui":
        return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                                "--server.port", port or "8501"], cwd=ROOT)
    if cmd == "api":
        return subprocess.call([sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1",
                                "--port", port or "8601"], cwd=ROOT)
    if cmd == "check":
        return subprocess.call([sys.executable, str(ROOT / "scripts" / "check_system.py")], cwd=ROOT)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
