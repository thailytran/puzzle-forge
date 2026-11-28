"""Variety gate for mystery series (owner 2026-11-21).

Every case must differ in puzzles, clue mechanic and games.

`check_series` returns a list of problems; an empty list means the series bible may be used.
Pure Python, no I/O besides `load_series`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_series(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


def check_series(series: dict[str, Any]) -> list[str]:
    rules = series.get("variety_rules") or {}
    vols = sorted(series.get("volumes") or [], key=lambda v: v["no"])
    bad: list[str] = []
    max_sim = float(rules.get("consecutive_type_similarity_max", 0.5))
    need_new = int(rules.get("min_new_or_twisted_types", 2))
    lookback = int(rules.get("final_form_not_in_previous", 2))
    seen_types: set[str] = set()
    seen_mech: set[str] = set()
    seen_inspo: set[str] = set()
    seen_setting: set[str] = set()
    if rules.get("arc_clue_every_volume"):  # one long mystery runs under the single cases
        arc = series.get("series_arc") or {}
        if not (arc.get("secret") and arc.get("question")):
            bad.append("series_arc needs a secret and a question")
        found = [str((v.get("arc_clue") or {}).get("found", "")).strip() for v in vols]
        for v, f in zip(vols, found, strict=True):
            if not f:
                bad.append(
                    f"vol {v['no']} {v.get('title', '')}: no arc_clue (piece of the series secret)"
                )
        if len({f for f in found if f}) != len([f for f in found if f]):
            bad.append("arc_clue: two volumes hand out the same piece of the series secret")
    for i, v in enumerate(vols):
        tag = f"vol {v['no']} {v.get('title', '')}"
        games = set(v.get("games") or [])
        if len(games) < 6:
            bad.append(f"{tag}: needs at least 6 distinct game types, has {len(games)}")
        mech = str(v.get("clue_mechanic", "")).strip().lower()
        if not mech:
            bad.append(f"{tag}: clue_mechanic missing")
        elif rules.get("mechanic_unique", True) and mech in seen_mech:
            bad.append(f"{tag}: clue mechanic repeated ({mech})")
        seen_mech.add(mech)
        inspo = str((v.get("inspired_by") or {}).get("work", "")).strip().lower()
        if not inspo:
            bad.append(f"{tag}: inspired_by.work missing (public-domain source required)")
        elif inspo in seen_inspo:
            bad.append(f"{tag}: inspiration reused ({inspo})")
        seen_inspo.add(inspo)
        setting = str(v.get("setting", "")).strip().lower()
        if setting in seen_setting:
            bad.append(f"{tag}: setting reused")
        seen_setting.add(setting)
        if i > 0:
            prev = set(vols[i - 1].get("games") or [])
            sim = _jaccard(games, prev)
            if sim > max_sim:
                bad.append(
                    f"{tag}: game set too similar to vol {vols[i - 1]['no']} "
                    f"({sim:.2f} > {max_sim})"
                )
            for k in range(1, lookback + 1):
                if i - k >= 0 and v.get("final_form") == vols[i - k].get("final_form"):
                    bad.append(f"{tag}: final form repeats vol {vols[i - k]['no']}")
        fresh = {g for g in games if g not in seen_types}
        twisted = {
            g for g in games if g in seen_types and str((v.get("twists") or {}).get(g, "")).strip()
        }
        if i > 0 and len(fresh) + len(twisted) < need_new:
            bad.append(
                f"{tag}: only {len(fresh) + len(twisted)} new/twisted game types (need {need_new})"
            )
        seen_types |= games
    return bad
