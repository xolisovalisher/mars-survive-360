"""Run the test suite and write honest results to docs/test_results.json (+ docs/TEST_REPORT.md table).

    python scripts/run_tests.py            # all tests (unit, integration, functional, ui)
    python scripts/run_tests.py --quick    # unit + integration only
Counts are taken from pytest's JUnit XML — a failed or errored test is never reported as passed.
"""
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET  # parsing our own pytest output (trusted, local file)
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def main(argv):
    quick = "--quick" in argv
    suites = ["tests/unit", "tests/integration"] if quick else ["tests/unit", "tests/integration", "tests/functional",
                                                               "tests/regression", "tests/performance", "tests/ui"]
    DOCS.mkdir(exist_ok=True)
    xml = ROOT / "logs" / "pytest_junit.xml"
    xml.parent.mkdir(exist_ok=True)
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-m", "pytest", *suites, "-q", f"--junitxml={xml}", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True)
    dur = time.time() - t0
    print(proc.stdout[-8000:])
    print(proc.stderr[-2000:], file=sys.stderr)
    per_suite, failures = {}, []
    totals = dict(tests=0, passed=0, failed=0, errors=0, skipped=0)
    if xml.exists():
        root = ET.parse(xml).getroot()
        for tc in root.iter("testcase"):
            cls = tc.get("classname", "")
            suite = cls.split(".")[1] if cls.startswith("tests.") and "." in cls else "other"
            s = per_suite.setdefault(suite, dict(tests=0, passed=0, failed=0, errors=0, skipped=0))
            outcome = "passed"
            if tc.find("failure") is not None:
                outcome = "failed"
            elif tc.find("error") is not None:
                outcome = "errors"
            elif tc.find("skipped") is not None:
                outcome = "skipped"
            for d in (s, totals):
                d["tests"] += 1
                d[outcome] += 1
            if outcome in ("failed", "errors"):
                failures.append(f"{cls}::{tc.get('name')}")
    res = {"when": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "mode": "quick" if quick else "full",
           "duration_s": round(dur, 1), "exit_code": proc.returncode, **totals, "by_suite": per_suite,
           "failures": failures, "python": sys.version.split()[0]}
    (DOCS / "test_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("mode", "tests", "passed", "failed", "errors", "skipped", "duration_s")}))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
