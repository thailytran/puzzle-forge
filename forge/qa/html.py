# ruff: noqa: E501  (inline CSS/HTML template)
"""Self-contained qa_report.html: summary, every check with evidence, page thumbnails."""

from __future__ import annotations

import html
from pathlib import Path

from forge.qa.report import QA_DIR, QaReport

CSS = """
:root{--ok:#1b7f3b;--bad:#b3261e;--warn:#9a6700;--mut:#666;--bg:#fff;--line:#ddd}
body{font:14px/1.45 system-ui,sans-serif;margin:24px auto;max-width:1100px;padding:0 16px;background:var(--bg)}
h1{margin:0 0 4px}.mut{color:var(--mut)}table{border-collapse:collapse;width:100%;margin:16px 0}
td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.b{display:inline-block;padding:1px 8px;border-radius:10px;color:#fff;font-weight:600;font-size:12px}
.pass{background:var(--ok)}.fail{background:var(--bad)}.skip{background:#888}.waived{background:var(--warn)}
.big{font-size:20px;padding:4px 14px}ul{margin:4px 0 0 18px;padding:0}
.thumbs{display:flex;flex-wrap:wrap;gap:10px}.thumbs figure{margin:0;text-align:center;font-size:12px}
.thumbs img{width:150px;border:1px solid var(--line)}.thumbs figure.flag img{border:3px solid var(--bad)}
"""


def _badge(status: str, waived: bool = False) -> str:
    cls = "waived" if waived else status
    label = "WAIVED" if waived else status.upper()
    return f'<span class="b {cls}">{label}</span>'


def render_html(report: QaReport, out_dir: Path) -> Path:
    e = html.escape
    flagged: set[int] = set()
    rows = []
    for c in report.checks:
        items = []
        for f in c.findings[:50]:
            page = f.evidence.get("page")
            if isinstance(page, int):
                flagged.add(page)
                link = f' <a href="#p{page}">page {page}</a>'
            else:
                link = ""
            items.append(f"<li>{e(f.message)}{link}</li>")
        more = f"<li class=mut>… {len(c.findings) - 50} more</li>" if len(c.findings) > 50 else ""
        detail = f"<ul>{''.join(items)}{more}</ul>" if items else e(c.message)
        rows.append(
            f"<tr><td>{_badge(c.status, c.waived)}</td><td><b>{e(c.id)}</b></td>"
            f"<td>{e(c.level)}</td><td>{detail}</td></tr>"
        )
    thumbs = []
    prev = sorted((out_dir / "previews").glob("page-*.png"))
    for img in prev:
        n = int(img.stem.split("-")[1])
        cls = ' class="flag"' if n in flagged else ""
        thumbs.append(
            f'<figure id="p{n}"{cls}><a href="../previews/{img.name}">'
            f'<img loading="lazy" src="../previews/{img.name}" alt="page {n}"></a>'
            f"<figcaption>{n}</figcaption></figure>"
        )
    c = report.counts
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>QA {e(report.book_id)}</title>
<style>{CSS}</style></head><body>
<h1>QA report — {e(report.book_id)}</h1>
<p>{_badge("pass" if report.result == "PASSED" else "fail").replace('class="b', 'class="b big')}
&nbsp; {c["blocker_fail"]} blocker · {c["major_fail"]} major · {c["minor_fail"]} minor fails ·
{c["waived"]} waived · {c["passed"]} passed · {c["skipped"]} skipped · auto-fix rounds: {report.fix_rounds}</p>
<p class="mut">run {e(report.run_id)} · {e(report.started)} → {e(report.finished)}<br>
locked hashes: {"; ".join(f"{k}={(v or '-')[:16]}" for k, v in report.hashes.items())}</p>
<table><tr><th>Status</th><th>Check</th><th>Level</th><th>Findings / evidence</th></tr>
{"".join(rows)}</table>
<h2>Pages</h2><div class="thumbs">{"".join(thumbs) or '<p class="mut">no thumbnails</p>'}</div>
</body></html>"""
    p = out_dir / QA_DIR / "qa_report.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return p
