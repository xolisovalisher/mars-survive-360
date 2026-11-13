"""Mission Reports (module 23): PDF, HTML, CSV, JSON, Excel.

`report` is a plain dict assembled by the UI/pipeline:
  {"title", "lang", "generated", "mission": {...}, "region", "data_class", "sections": [
      {"key": "route", "title": "...", "kv": {...}, "table": [ {...}, ... ], "image": "png bytes", "notes": [...]}, ...]}
HTML output escapes every value (no uncontrolled user text in HTML).
PDF uses bundled/system Unicode fonts with HarfBuzz shaping (Arabic, Devanagari);
if no font for a script is found, the PDF says so and the HTML report remains complete.
"""
from __future__ import annotations

import html
import io
import math
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config as C

FONT_DIR = C.ROOT / "assets" / "fonts"

CJK_CANDIDATES = {
    "zh": [("C:/Windows/Fonts/msyh.ttc", 0), ("C:/Windows/Fonts/simsun.ttc", 0),
           ("/System/Library/Fonts/PingFang.ttc", 0), ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2)],
    "ja": [("C:/Windows/Fonts/YuGothM.ttc", 0), ("C:/Windows/Fonts/meiryo.ttc", 0), ("C:/Windows/Fonts/msgothic.ttc", 0),
           ("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc", 0), ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0)],
    "ko": [("C:/Windows/Fonts/malgun.ttf", 0), ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
           ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1)],
}


def _font_for(lang: str):
    """Return (path, collection index) for the language's script or None."""
    if lang in CJK_CANDIDATES:
        for p, i in CJK_CANDIDATES[lang]:
            if Path(p).exists():
                return p, i
        return None
    if lang == "hi":
        for p in ["C:/Windows/Fonts/Nirmala.ttf", str(FONT_DIR / "NotoSansDevanagari-Regular.ttf")]:
            if Path(p).exists():
                return p, 0
        return None
    if lang == "ar":
        p = FONT_DIR / "NotoSansArabic-Regular.ttf"
        return (str(p), 0) if p.exists() else None
    p = FONT_DIR / "DejaVuSans.ttf"
    return (str(p), 0) if p.exists() else None


def _flatten(report: dict, tables: bool = False) -> list[dict]:
    """Long format: one row per value. Key–value facts have an empty 'row'; with tables=True every table cell is
    added as (section, row number, column, value)."""
    rows = []
    for s in report.get("sections", []):
        title = s.get("title", s.get("key"))
        for k, v in (s.get("kv") or {}).items():
            rows.append({"section": title, "row": "", "item": k, "value": v})
        if tables:
            for i, r in enumerate(s.get("table") or [], 1):
                for k, v in (r.items() if isinstance(r, dict) else []):
                    rows.append({"section": title, "row": i, "item": k, "value": v})
    return rows


def to_json(report: dict) -> bytes:
    def default(o):
        if hasattr(o, "tolist"):
            return o.tolist()
        if isinstance(o, (bytes, bytearray)):
            return None
        return str(o)
    clean = {**report, "sections": [{k: v for k, v in s.items() if k != "image"} for s in report.get("sections", [])]}
    return json.dumps(clean, ensure_ascii=False, indent=2, default=default).encode("utf-8")


def to_csv(report: dict) -> bytes:
    return pd.DataFrame(_flatten(report, tables=True), columns=["section", "row", "item", "value"]).to_csv(
        index=False).encode("utf-8-sig")


def to_excel(report: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame([{"field": k, "value": str(v)} for k, v in report.get("mission", {}).items()]).to_excel(
            xw, sheet_name="mission", index=False)
        pd.DataFrame(_flatten(report)).to_excel(xw, sheet_name="summary", index=False)
        for s in report.get("sections", []):
            if s.get("table"):
                name = str(s.get("key", "t"))[:28]
                pd.DataFrame(s["table"]).to_excel(xw, sheet_name=name, index=False)
    return buf.getvalue()


def to_html(report: dict) -> bytes:
    import base64
    e = html.escape
    rtl = report.get("rtl", False)
    parts = [f"<!DOCTYPE html><html lang='{e(report.get('lang', 'en'))}' dir='{'rtl' if rtl else 'ltr'}'><head>"
             "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{e(report.get('title', ''))}</title><style>"
             "body{font-family:system-ui,'Segoe UI','Noto Sans',sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;"
             "color:#e8ecf3;background:#0b0f17}h1{color:#ff7a45}h2{border-bottom:1px solid #2a3446;padding-bottom:4px;"
             "color:#ffb38a}table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}td,th{border:1px solid #2a3446;"
             "padding:4px 6px;text-align:start}th{background:#151c2a}.badge{display:inline-block;padding:2px 8px;border-radius:8px;"
             "background:#3a1d14;color:#ffb38a;font-size:12px}img{max-width:100%;border:1px solid #2a3446}.note{color:#9fb0c8;"
             "font-size:12px}</style></head><body>",
             f"<h1>{e(report.get('title', ''))}</h1>",
             f"<p><span class='badge'>{e(str(report.get('data_class', '')))}</span> "
             f"{e(report.get('region', ''))} · {e(report.get('generated', ''))}</p>"]
    if report.get("mission"):
        parts.append("<table>" + "".join(f"<tr><th>{e(str(k))}</th><td>{e(str(v))}</td></tr>"
                                        for k, v in report["mission"].items()) + "</table>")
    for s in report.get("sections", []):
        parts.append(f"<h2>{e(s.get('title', ''))}</h2>")
        if s.get("kv"):
            parts.append("<table>" + "".join(f"<tr><th>{e(str(k))}</th><td>{e(str(v))}</td></tr>"
                                            for k, v in s["kv"].items()) + "</table>")
        if s.get("image"):
            parts.append(f"<img alt='' src='data:image/png;base64,{base64.b64encode(s['image']).decode()}'>")
        if s.get("table"):
            df = pd.DataFrame(s["table"])
            parts.append(df.to_html(index=False, escape=True, border=0))
        for n in s.get("notes", []):
            parts.append(f"<p class='note'>{e(str(n))}</p>")
    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")


def to_pdf(report: dict) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    lang = report.get("lang", "en")
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(True, margin=14)
    fams = []
    main = _font_for(lang)
    lang_ok = main is not None
    if not lang_ok:
        main = _font_for("en")
    pdf.add_font("Main", "", main[0], collection_font_number=main[1])
    fams.append("Main")
    dj = FONT_DIR / "DejaVuSans.ttf"
    if dj.exists() and str(dj) != main[0]:
        pdf.add_font("DejaVu", "", str(dj))
        fams.append("DejaVu")
    pdf.set_fallback_fonts([f for f in fams if f != "Main"])
    try:
        pdf.set_text_shaping(True)
    except Exception:  # noqa: BLE001 - uharfbuzz missing: Arabic/Devanagari would not join correctly
        pass
    rtl = report.get("rtl", False)
    align = "R" if rtl else "L"
    pdf.add_page()
    pdf.set_font("Main", size=16)
    pdf.set_text_color(200, 70, 30)
    pdf.multi_cell(0, 9, str(report.get("title", "")), align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Main", size=9)
    pdf.multi_cell(0, 5, f"{report.get('data_class', '')} | {report.get('region', '')} | {report.get('generated', '')}",
                   align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if not lang_ok:
        pdf.multi_cell(0, 5, f"[No font for '{lang}' found on this computer - see the HTML report for full text]",
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def kv_table(d: dict):
        pdf.set_font("Main", size=9)
        for k, v in d.items():
            pdf.set_fill_color(240, 236, 232)
            x0 = pdf.get_x()
            pdf.multi_cell(65, 5.5, str(k)[:70], border=1, fill=True, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP,
                           max_line_height=5.5)
            pdf.multi_cell(0, 5.5, str(v)[:160], border=1, align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                           max_line_height=5.5)
            pdf.set_x(x0)

    if report.get("mission"):
        kv_table(report["mission"])
    for s in report.get("sections", []):
        pdf.ln(3)
        pdf.set_font("Main", size=12)
        pdf.set_text_color(160, 60, 20)
        pdf.multi_cell(0, 7, str(s.get("title", "")), align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(30, 30, 30)
        if s.get("kv"):
            kv_table(s["kv"])
        if s.get("image"):
            if pdf.get_y() > 180:
                pdf.add_page()
            pdf.image(io.BytesIO(s["image"]), w=180)
        if s.get("table"):
            df = pd.DataFrame(s["table"]).head(25)
            cols = list(df.columns)[:7]
            pdf.set_font("Main", size=7)
            from fpdf.fonts import FontFace
            with pdf.table(col_widths=tuple([1] * len(cols)), text_align="CENTER", line_height=4.5,
                           headings_style=FontFace(emphasis="", fill_color=(235, 225, 215))) as tb:
                row = tb.row()
                for c in cols:
                    row.cell(str(c)[:24])
                for _, r in df[cols].iterrows():
                    row = tb.row()
                    for c in cols:
                        v = r[c]
                        row.cell(f"{v:.3g}" if isinstance(v, float) else str(v)[:40])
        for n in s.get("notes", []):
            pdf.set_font("Main", size=8)
            pdf.multi_cell(0, 4.5, str(n), align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def save_all(report: dict, stem: str | None = None) -> dict:
    stem = stem or "mission_report_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = {}
    for ext, fn in (("pdf", to_pdf), ("html", to_html), ("csv", to_csv), ("json", to_json), ("xlsx", to_excel)):
        p = C.REPORTS_DIR / f"{stem}.{ext}"
        p.write_bytes(fn(report))
        out[ext] = str(p)
    return out


def chart_png(x, ys: dict, xlabel="", ylabel="", hline=None, figsize=(7.5, 2.6)) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize, dpi=130)
    for name, y in ys.items():
        ax.plot(x, y, label=name, lw=1.6)
    if hline is not None:
        ax.axhline(hline, color="red", ls="--", lw=1)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.3)
    if len(ys) > 1:
        ax.legend(fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def map_png(grid, hillshade, routes: dict, hazard_level=None, targets=None) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (s, w), (n, e) = grid.bounds
    fig, ax = plt.subplots(figsize=(7.5, 6), dpi=130)
    asp = 1 / max(0.2, math.cos(math.radians((s + n) / 2)))
    ax.imshow(hillshade, cmap="gray", extent=[w, e, s, n], aspect=asp)
    if hazard_level is not None:
        import numpy as np
        hz = np.ma.masked_where(hazard_level == 0, hazard_level)
        ax.imshow(hz, cmap="autumn_r", alpha=0.45, extent=[w, e, s, n], aspect=asp, vmin=1, vmax=4)
    from mars_survive.mapping.views import ROUTE_COLORS
    for name, r in routes.items():
        if r is not None and r.found:
            ax.plot(r.lon, r.lat, color=ROUTE_COLORS.get(name, "yellow"), lw=2, label=name)
    for tg in targets or []:
        ax.plot(tg["lon"], tg["lat"], "o", color="cyan", ms=4)
    ax.set_xlabel("lon (°E)")
    ax.set_ylabel("lat (°N)")
    if routes:
        ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def system_info() -> str:
    return f"{platform.system()} {platform.release()} / Python {platform.python_version()} / pid {os.getpid()}"
