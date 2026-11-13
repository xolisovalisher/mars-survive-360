"""System check: Python version, required/optional libraries, project modules, folders, data and free resources.
Exit code 0 = ready, 1 = a required item is missing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if sys.version_info < (3, 10):
        print(f"[FAIL] Python {sys.version.split()[0]} — 3.10+ required")
        return 1
    from mars_survive.diagnostics import checks
    ok = True
    print(f"[OK]   Python {sys.version.split()[0]}")
    for lib in checks.libraries():
        mark = "OK  " if lib["ok"] else ("WARN" if lib["optional"] else "FAIL")
        ok &= bool(lib["ok"] or lib["optional"])
        print(f"[{mark}] {lib['library']:<16} {lib.get('version') or ''} {lib.get('error') or ''}")
    for m in checks.modules_health():
        ok &= bool(m["ok"])
        print(f"[{'OK  ' if m['ok'] else 'FAIL'}] module {m['module']} {m.get('error') or ''}")
    for d in checks.directories():
        print(f"[{'OK  ' if d['exists'] and d['writable'] else 'WARN'}] dir {d['path']}")
    for k, v in checks.data_assets().items():
        print(f"[INFO] data {k}: {v}")
    print("[INFO] no real DEM yet -> app runs on the labelled SYNTHETIC DEM; run scripts/download_data.py"
          if not checks.data_assets()["dem_processed"] else "[OK]   processed DEM present")
    r = checks.resources()
    print(f"[INFO] resources {r}")
    print("READY" if ok else "NOT READY — install missing required packages: pip install -r requirements.txt")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
