"""Build locales/*.json from the translation sources in mars_survive/localization/src/.

en.txt   : '@section' lines and 'key = value' lines (the master list).
<xx>.txt : the same '@section' lines, each followed by ONLY the translated values,
           one per line, in the same order as in en.txt.
Checks: section names, value counts per section, {placeholders} identical to English.
Exit code 1 on any problem (so CI/tests catch it).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mars_survive" / "localization" / "src"
OUT = ROOT / "mars_survive" / "localization" / "locales"
PH = re.compile(r"\{(\w+)\}")


def read_master():
    sections, cur = {}, None
    for ln in (SRC / "en.txt").read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        if ln.startswith("@"):
            cur = ln[1:].strip()
            sections[cur] = []
            continue
        k, v = ln.split(" = ", 1)
        sections[cur].append((k.strip(), v.replace("\\n", "\n")))
    return sections


def read_lang(path: Path):
    sections, cur = {}, None
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        if ln.startswith("@"):
            cur = ln[1:].strip()
            sections[cur] = []
            continue
        sections[cur].append(ln.replace("\\n", "\n").strip())
    return sections


def main() -> int:
    master = read_master()
    OUT.mkdir(parents=True, exist_ok=True)
    en = {k: v for sec in master.values() for k, v in sec}
    dup = len([k for sec in master.values() for k, _ in sec]) - len(en)
    problems = [f"en: {dup} duplicate keys"] if dup else []
    (OUT / "en.json").write_text(json.dumps(en, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in sorted(SRC.glob("*.txt")):
        code = p.stem
        if code == "en":
            continue
        lang = read_lang(p)
        out = {}
        for sec, items in master.items():
            vals = lang.get(sec)
            if vals is None:
                problems.append(f"{code}: missing section @{sec}")
                continue
            if len(vals) != len(items):
                problems.append(f"{code}: @{sec} has {len(vals)} values, expected {len(items)}")
            for (k, ev), tv in zip(items, vals):
                if set(PH.findall(ev)) != set(PH.findall(tv)):
                    problems.append(f"{code}: placeholder mismatch in {k}: {tv!r}")
                out[k] = tv
        extra = set(lang) - set(master)
        if extra:
            problems.append(f"{code}: unknown sections {sorted(extra)}")
        (OUT / f"{code}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{code}: {len(out)}/{len(en)} keys")
    for pr in problems:
        print("PROBLEM:", pr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
