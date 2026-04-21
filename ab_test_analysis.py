"""
A/B Test Analysis Pipeline (3-arm e-commerce experiment)
========================================================

Data model (events.csv):
    event_id, timestamp, customer_id, session_id, event_type,
    product_id, device_type, traffic_source, campaign_id,
    page_category, session_duration_sec, experiment_group

Experimental design:
    - experiment_group in {Control, Variant_A, Variant_B}
    - Unit of analysis: session_id
    - Group assignment per session: MODAL experiment_group across that
      session's events (ties broken by first-seen order).
    - Sessions whose events disagree about the group are flagged as
      "assignment contamination" -- they are KEPT via modal rule but
      reported as a data-quality finding.
    - Outcome: session converted if it contains any `purchase` event.

Tests performed:
    1) Variant_A vs Control (two-proportion z-test)
    2) Variant_B vs Control (two-proportion z-test)
Both tests run two-sided at alpha = 0.05 with Bonferroni correction
(effective alpha = 0.025) because we run 2 comparisons on the same control.

Outputs:
    data/results.json
    images/conversion_rate.png
    images/daily_trend.png
    images/confidence_interval.png
    images/sample_growth.png

Run: python ab_test_analysis.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.stats.proportion import (
    proportions_ztest,
    proportion_confint,
    confint_proportions_2indep,
    proportion_effectsize,
)
from statsmodels.stats.power import NormalIndPower

# ---------- paths ----------
HERE = Path(__file__).resolve().parent
_default_candidates = [
    Path(os.environ["AB_EVENTS_CSV"]) if os.environ.get("AB_EVENTS_CSV") else None,
    HERE / "data" / "events.csv",
    HERE.parent / "1" / "events.csv",
]
EVENTS_PATH = next((p for p in _default_candidates if p and p.exists()), None)
if EVENTS_PATH is None:
    raise FileNotFoundError(
        "events.csv not found. Put it in data/events.csv, ../1/events.csv, "
        "or set AB_EVENTS_CSV environment variable."
    )

IMG_DIR = HERE / "images"
RESULTS_PATH = HERE / "data" / "results.json"
IMG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

ALPHA_FAMILY = 0.05
N_COMPARISONS = 2
ALPHA_ADJ = ALPHA_FAMILY / N_COMPARISONS  # Bonferroni

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130,
    "figure.figsize": (8.5, 5),
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.labelsize": 11, "font.size": 10,
})
COLOR = {"Control": "#6b7280", "Variant_A": "#F58518", "Variant_B": "#4C78A8"}

# ---------- 1. load ----------
print(f"[load] Reading {EVENTS_PATH} ...")
ev = pd.read_csv(EVENTS_PATH, parse_dates=["timestamp"])
ev["date"] = ev["timestamp"].dt.date
N_EVENTS = len(ev)
print(f"[load] {N_EVENTS:,} events, "
      f"{ev['session_id'].nunique():,} sessions, "
      f"{ev['customer_id'].nunique():,} customers")

# ---------- 2. data quality ----------
group_counts = ev.groupby(["session_id", "experiment_group"]).size().unstack(fill_value=0)
sess_group_nunique = (group_counts > 0).sum(axis=1)
n_sessions = int(group_counts.shape[0])
n_contaminated = int((sess_group_nunique > 1).sum())

ts_counts = ev["traffic_source"].value_counts()
lower_to_variants = {}
for name, cnt in ts_counts.items():
    lower_to_variants.setdefault(name.lower(), []).append((name, int(cnt)))
case_inconsistencies = {k: v for k, v in lower_to_variants.items() if len(v) > 1}

# ---------- 3. session-level assignment (modal) ----------
modal_group = group_counts.idxmax(axis=1)
modal_share = group_counts.max(axis=1) / group_counts.sum(axis=1)

purchased = ev.groupby("session_id")["event_type"].apply(lambda s: (s == "purchase").any())
first_date = ev.groupby("session_id")["date"].min()

session = pd.DataFrame({
    "group": modal_group,
    "modal_share": modal_share,
    "converted": purchased.astype(int).reindex(modal_group.index, fill_value=0),
    "date": first_date,
}).reset_index()

# ---------- 4. group-level metrics ----------
grp = session.groupby("group")["converted"].agg(count="count", conv="sum", rate="mean")
grp = grp.reindex(["Control", "Variant_A", "Variant_B"])
print("\n[stats] Session-level conversion rate by group:")
print(grp)

def row(g):
    x = int(grp.loc[g, "conv"])
    n = int(grp.loc[g, "count"])
    p = float(grp.loc[g, "rate"])
    lo, hi = proportion_confint(x, n, alpha=0.05, method="wilson")
    return dict(n=n, conversions=x, rate=p,
                ci95_lower=float(lo), ci95_upper=float(hi))

control = row("Control")
vA = row("Variant_A")
vB = row("Variant_B")

# ---------- 5. pairwise tests ----------
def ztest_vs_control(variant_name):
    v = {"Variant_A": vA, "Variant_B": vB}[variant_name]
    c = control
    z, p2 = proportions_ztest(
        count=np.array([v["conversions"], c["conversions"]]),
        nobs=np.array([v["n"], c["n"]]),
        alternative="two-sided",
    )
    ci_lo, ci_hi = confint_proportions_2indep(
        count1=v["conversions"], nobs1=v["n"],
        count2=c["conversions"], nobs2=c["n"],
        method="wald",
    )
    abs_diff_pp = (v["rate"] - c["rate"]) * 100
    rel_lift_pct = (v["rate"] - c["rate"]) / c["rate"] * 100
    h = float(proportion_effectsize(v["rate"], c["rate"]))
    try:
        obs_power = float(NormalIndPower().solve_power(
            effect_size=abs(h), nobs1=v["n"], alpha=ALPHA_ADJ,
            ratio=c["n"] / v["n"], alternative="two-sided"))
    except Exception:
        obs_power = None
    return {
        "name": variant_name,
        "z_stat": float(z),
        "p_value_two_sided": float(p2),
        "p_value_bonferroni": float(min(p2 * N_COMPARISONS, 1.0)),
        "alpha_bonferroni": ALPHA_ADJ,
        "diff_ci95_lower": float(ci_lo),
        "diff_ci95_upper": float(ci_hi),
        "abs_diff_pp": abs_diff_pp,
        "rel_lift_pct": rel_lift_pct,
        "cohens_h": h,
        "observed_power": obs_power,
        "decision_en": (
            "Reject H0 (significantly different from Control)"
            if p2 * N_COMPARISONS < ALPHA_FAMILY else
            "Fail to reject H0"
        ),
        "direction_en": (
            "higher than Control" if abs_diff_pp > 0 else
            ("lower than Control" if abs_diff_pp < 0 else "equal to Control")
        ),
    }

test_A = ztest_vs_control("Variant_A")
test_B = ztest_vs_control("Variant_B")

print(f"\n[test] Variant_A vs Control: z={test_A['z_stat']:.3f}, "
      f"p={test_A['p_value_two_sided']:.4g}, "
      f"diff={test_A['abs_diff_pp']:+.2f} pp, lift={test_A['rel_lift_pct']:+.2f}%, "
      f"=> {test_A['decision_en']}")
print(f"[test] Variant_B vs Control: z={test_B['z_stat']:.3f}, "
      f"p={test_B['p_value_two_sided']:.4g}, "
      f"diff={test_B['abs_diff_pp']:+.2f} pp, lift={test_B['rel_lift_pct']:+.2f}%, "
      f"=> {test_B['decision_en']}")

# ---------- 6. charts ----------
def fmt_pct(x, _): return f"{x * 100:.1f}%"

def plot_bars():
    fig, ax = plt.subplots()
    order = ["Control", "Variant_A", "Variant_B"]
    data = [control, vA, vB]
    colors = [COLOR[g] for g in order]
    rates = [d["rate"] for d in data]
    err_lo = [d["rate"] - d["ci95_lower"] for d in data]
    err_hi = [d["ci95_upper"] - d["rate"] for d in data]
    bars = ax.bar(order, rates, color=colors, width=0.55,
                  yerr=[err_lo, err_hi], capsize=6, ecolor="black")
    for bar, r in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, r + 0.002,
                f"{r * 100:.2f}%", ha="center", va="bottom", fontsize=11)
    ax.set_ylabel("Session-level conversion rate")
    ax.set_title("Conversion rate by experiment group (95% CI)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt_pct))
    ax.set_ylim(0, max(rates) * 1.2)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "conversion_rate.png")
    plt.close(fig)

def plot_daily_trend():
    daily = (session.groupby(["date", "group"])["converted"].mean()
                    .unstack("group")).sort_index()
    fig, ax = plt.subplots()
    for g in ["Control", "Variant_A", "Variant_B"]:
        if g in daily.columns:
            ax.plot(daily.index, daily[g].rolling(14, min_periods=1).mean(),
                    label=g, color=COLOR[g], linewidth=1.5)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt_pct))
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily conversion rate (14-day rolling mean)")
    ax.set_title("Conversion rate trend over time")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(IMG_DIR / "daily_trend.png")
    plt.close(fig)

def plot_ci():
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ys = [1, 0]
    labels = ["Variant_A vs Control", "Variant_B vs Control"]
    tests = [test_A, test_B]
    for y, lab, t in zip(ys, labels, tests):
        lo = t["diff_ci95_lower"] * 100
        hi = t["diff_ci95_upper"] * 100
        mid = t["abs_diff_pp"]
        col = COLOR["Variant_A"] if "Variant_A" in lab else COLOR["Variant_B"]
        ax.errorbar([mid], [y], xerr=[[mid - lo], [hi - mid]],
                    fmt="o", color=col, capsize=8, markersize=9, linewidth=2)
        ax.text(hi + 0.05, y, f"  {mid:+.2f} pp  (p={t['p_value_two_sided']:.2e})",
                va="center", fontsize=10)
    ax.axvline(0, color="black", linestyle="--", linewidth=1)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Difference in conversion rate vs Control (percentage points)")
    ax.set_title("95% CI of variant-vs-control differences")
    ax.set_ylim(-0.6, 1.6)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "confidence_interval.png")
    plt.close(fig)

def plot_sample_growth():
    cum = (session.groupby(["date", "group"]).size()
                  .unstack("group", fill_value=0).sort_index().cumsum())
    fig, ax = plt.subplots()
    for g in ["Control", "Variant_A", "Variant_B"]:
        if g in cum.columns:
            ax.plot(cum.index, cum[g], label=g, color=COLOR[g], linewidth=2)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative sessions")
    ax.set_title("Traffic allocation over time")
    ax.legend(frameon=False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, _: f"{int(x/1000)}k" if x >= 1000 else f"{int(x)}"
    ))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(IMG_DIR / "sample_growth.png")
    plt.close(fig)

plot_bars()
plot_daily_trend()
plot_ci()
plot_sample_growth()

# ---------- 7. persist results ----------
results = {
    "dataset": {
        "events": N_EVENTS,
        "sessions": n_sessions,
        "customers": int(ev["customer_id"].nunique()),
        "contaminated_sessions": n_contaminated,
        "contamination_rate_pct": round(n_contaminated / n_sessions * 100, 2),
        "start_date": str(ev["timestamp"].min().date()),
        "end_date": str(ev["timestamp"].max().date()),
        "traffic_source_case_inconsistencies": case_inconsistencies,
    },
    "groups": {
        "Control": control,
        "Variant_A": vA,
        "Variant_B": vB,
    },
    "tests": {
        "alpha_family": ALPHA_FAMILY,
        "alpha_adjusted_bonferroni": ALPHA_ADJ,
        "Variant_A_vs_Control": test_A,
        "Variant_B_vs_Control": test_B,
    },
}

with open(RESULTS_PATH, "w", encoding="utf-8") as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2, default=str)

print(f"\n[OK] Wrote results -> {RESULTS_PATH}")
print(f"[OK] Wrote images -> {IMG_DIR}")
