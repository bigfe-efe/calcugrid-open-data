#!/usr/bin/env python3
"""
Re-run the invariants on the published files.

    python verify.py

No dependencies — standard library only. This is the same class of check the
data passes before publication, rewritten against the CSVs so anyone can run it
without trusting a claim in a README.

It does not prove the data is correct. It proves a specific set of silent
failure modes is absent: a unit read the wrong way, an inverted scale entered
as a normal one, a grade band that covers nothing, a tax bracket that runs
backwards.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
problems: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def rows(name: str) -> list[dict]:
    with (HERE / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def check_dogs() -> int:
    data = rows("dog-breed-standards.csv")
    for r in data:
        tag = f"[dog/{r['slug']}]"
        lo, hi = num(r["min_kg"]), num(r["max_kg"])
        if lo is None or hi is None:
            fail(f"{tag} missing weight")
            continue
        if lo > hi:
            fail(f"{tag} min above max")
        # The units question. A dog at 90 kg would be a conversion error, not
        # an animal — the heaviest AKC breeds top out around 80.
        if not 0.5 <= lo <= 100 or not 0.5 <= hi <= 120:
            fail(f"{tag} implausible weight {lo}-{hi} kg — check units")
        lb_lo, lb_hi = num(r["min_lb"]), num(r["max_lb"])
        for kg, lb in ((lo, lb_lo), (hi, lb_hi)):
            if lb is None or abs(kg * 2.2046226218 - lb) > 0.2:
                fail(f"{tag} pound column does not match the kilogram column")
        # RER = 70 * kg^0.75, times 1.6 for a neutered adult.
        mid, kcal = num(r["midpoint_kg"]), num(r["daily_kcal_neutered_adult_at_midpoint"])
        if mid and kcal and abs(70 * mid**0.75 * 1.6 - kcal) > 1.5:
            fail(f"{tag} calories do not follow 70 * kg^0.75 * 1.6")
    return len(data)


def check_grading() -> int:
    scales = {r["slug"]: r for r in rows("grading-scales.csv")}
    bands = rows("grading-scale-bands.csv")

    by_country: dict[str, list[dict]] = {}
    for b in bands:
        by_country.setdefault(b["country_slug"], []).append(b)

    for slug, scale in scales.items():
        tag = f"[grade/{slug}]"
        group = by_country.get(slug)
        if not group:
            fail(f"{tag} no bands")
            continue

        higher_is_better = scale["higher_is_better"].lower() == "true"
        lo, hi = num(scale["scale_min"]), num(scale["scale_max"])

        ordered = sorted(group, key=lambda b: num(b["grade_from"]))
        if abs(num(ordered[0]["grade_from"]) - lo) > 1e-9:
            fail(f"{tag} bands do not start at the bottom of the scale")
        if abs(num(ordered[-1]["grade_to"]) - hi) > 1e-9:
            fail(f"{tag} bands do not reach the top of the scale")

        # Ordered best-first, the GPA column must descend. This is the check
        # that catches an inverted scale entered as a normal one.
        best_first = sorted(
            group, key=lambda b: num(b["grade_from"]), reverse=higher_is_better
        )
        gpas = [num(b["us_gpa_convention"]) for b in best_first]
        if gpas != sorted(gpas, reverse=True):
            fail(f"{tag} GPA does not descend from the best grade — direction is wrong")
        if gpas[0] != 4.0:
            fail(f"{tag} the best band is {gpas[0]}, not 4.0")
        if gpas[-1] != 0.0:
            fail(f"{tag} the worst band is {gpas[-1]}, not 0.0")

        mark = num(scale["pass_mark"])
        if mark is None or not lo <= mark <= hi:
            fail(f"{tag} pass mark {mark} is outside the scale")

        if int(scale["band_count"]) != len(group):
            fail(f"{tag} band_count says {scale['band_count']}, found {len(group)}")

    inverted = [s for s, r in scales.items() if r["higher_is_better"].lower() == "false"]
    if len(inverted) != 4:
        fail(f"expected 4 inverted scales, found {len(inverted)}: {inverted}")

    return len(scales)


def check_tax() -> int:
    brackets = rows("us-state-tax-brackets-2026.csv")
    by_key: dict[tuple[str, str], list[dict]] = {}
    for b in brackets:
        by_key.setdefault((b["state_slug"], b["filing_status"]), []).append(b)

    for (state, status), group in by_key.items():
        tag = f"[tax/{state}/{status}]"
        group.sort(key=lambda b: int(b["bracket_index"]))
        previous_rate = -1.0
        previous_to = None
        for b in group:
            frm, to, rate = num(b["income_from_usd"]), num(b["income_to_usd"]), num(b["marginal_rate"])
            if rate is None or not 0 <= rate <= 0.15:
                fail(f"{tag} implausible marginal rate {rate}")
            # A progressive schedule never steps down.
            if rate < previous_rate - 1e-12:
                fail(f"{tag} marginal rate falls as income rises")
            previous_rate = rate
            if previous_to is not None and abs(frm - previous_to) > 1e-9:
                fail(f"{tag} gap or overlap between brackets at {frm}")
            if to is not None and to <= frm:
                fail(f"{tag} bracket ends at or below where it starts")
            previous_to = to
        if group[-1]["income_to_usd"] not in ("", None):
            fail(f"{tag} the top bracket is bounded — it should be open-ended")

    summary = rows("us-state-income-tax-2026.csv")
    for r in summary:
        tag = f"[tax/{r['slug']}]"
        if r["system"] not in ("progressive", "flat", "none"):
            fail(f"{tag} unknown system {r['system']!r}")
        if (r["system"] == "none") != (r["has_income_tax"].lower() == "false"):
            fail(f"{tag} system and has_income_tax disagree")
        net = num(r["net_pay_at_100k_usd"])
        if net is None or not 55_000 <= net <= 90_000:
            fail(f"{tag} implausible net pay on $100k: {net}")
    return len(summary)


def check_gpu() -> int:
    data = rows("gpu-power-specs.csv")
    for r in data:
        tag = f"[gpu/{r['slug']}]"
        tgp, psu = num(r["total_graphics_power_w"]), num(r["recommended_psu_w"])
        if tgp is None or not 30 <= tgp <= 800:
            fail(f"{tag} implausible TGP {tgp} W")
        if psu is None or psu <= tgp:
            fail(f"{tag} recommended PSU does not clear the card's own draw")
    return len(data)


def check_ev() -> int:
    data = rows("ev-efficiency.csv")
    for r in data:
        tag = f"[ev/{r['slug']}]"
        kwh, rng = num(r["kwh_per_100_miles"]), num(r["epa_range_miles"])
        # The upper bound has to clear the GMC Hummer EV Pickup at 63.9, which
        # is a real EPA figure for a four-tonne truck rather than a data error.
        # Efficient sedans sit near 24; anything past 80 would be suspect.
        if kwh is None or not 15 <= kwh <= 80:
            fail(f"{tag} implausible consumption {kwh} kWh/100mi")
        if rng is None or not 80 <= rng <= 600:
            fail(f"{tag} implausible range {rng} mi")
    rates = rows("us-electricity-rates.csv")
    for r in rates:
        c = num(r["residential_cents_per_kwh"])
        if c is None or not 5 <= c <= 60:
            fail(f"[rate/{r['slug']}] implausible rate {c} cents/kWh")
    return len(data)


def check_self_employed() -> int:
    data = rows("us-1099-vs-w2-by-state.csv")
    negatives = []
    for r in data:
        tag = f"[1099/{r['slug']}]"
        net_1099 = num(r["net_1099_at_100k_usd"])
        net_w2 = num(r["net_w2_at_100k_usd"])
        diff = num(r["tax_difference_usd"])
        be = num(r["break_even_contract_usd"])
        premium = num(r["break_even_premium"])

        if net_1099 is None or not 55_000 <= net_1099 <= 85_000:
            fail(f"{tag} implausible 1099 take-home {net_1099}")
        if net_w2 is None or not 55_000 <= net_w2 <= 85_000:
            fail(f"{tag} implausible W-2 take-home {net_w2}")

        # The difference column must agree with the two take-home columns:
        # more tax means less kept, and the two gaps are the same number.
        if abs((net_w2 - net_1099) - diff) > 0.02:
            fail(f"{tag} tax_difference does not match the take-home columns")

        # The break-even premium must agree with the break-even value.
        if abs((be / 100_000 - 1) - premium) > 1e-4:
            fail(f"{tag} break_even_premium does not match break_even_contract")

        # A negative difference must come with a break-even BELOW the salary,
        # and vice versa — they are two views of the same fact.
        if (diff < 0) != (be < 100_000):
            fail(f"{tag} the sign of the difference contradicts the break-even")

        if diff < 0:
            negatives.append(r["state"])

    # California is the documented case where contracting costs less. If that
    # set ever changes, the README's explanation needs revisiting.
    if negatives != ["California"]:
        fail(f"states where contracting costs less tax changed: {negatives}")

    return len(data)


def main() -> int:
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for name in manifest["files"]:
        if not (HERE / name).exists():
            fail(f"manifest lists {name}, which is missing")

    counts = {
        "dog breeds": check_dogs(),
        "grading scales": check_grading(),
        "states": check_tax(),
        "GPUs": check_gpu(),
        "EVs": check_ev(),
        "states of 1099 comparison": check_self_employed(),
    }

    print(f"  checked: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    if problems:
        print(f"\n  FAILED — {len(problems)} problem(s):", file=sys.stderr)
        for p in problems[:40]:
            print(f"    - {p}", file=sys.stderr)
        return 1
    print("  all invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
