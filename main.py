"""GTA VI Trophy Rarity Forecaster
Model: Per-trophy logit-linear trend on log-time + class shrinkage + anchored median.
"""

import json
import math
import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

# I/O setup
INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
RELEASE_R = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]


def clamp_p(p: float) -> float:
    return min(99.99, max(0.01, p))


def logit(p: float) -> float:
    p_clamped = clamp_p(p)
    return math.log(p_clamped / (100 - p_clamped))


def expit(y: float) -> float:
    return 100 / (1 + math.exp(-y))


def round4(x: float) -> float | int:
    """Round to 4 decimals, half-up."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if value.is_integer() else value


def get_hours_from_r(dt_str: str) -> float:
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    delta = dt - RELEASE_R
    hours = delta.total_seconds() / 3600
    return max(0.0, hours)


def get_x(dt_str: str) -> float:
    return math.log(1 + get_hours_from_r(dt_str))


def get_class(description: str) -> str:
    desc = description.lower()
    # Story
    if "chapter" in desc or "final mission" in desc:
        return "story"
    if desc.startswith("complete ") and not any(c.isdigit() for c in desc):
        return "story"
    # Grind
    grind_keywords = [
        "250 stunts", "100 locations", "50 challenges", "20 different races",
        "100 vehicles", "10 vehicles", "5 bank vaults", "8 mission strands",
        "3 collectible card sets", "gold medal in all", "every location", "every spot"
    ]
    if any(k in desc for k in grind_keywords):
        return "grind"
    # Explore
    explore_keywords = ["explore all", "discover", "meditate at every"]
    if any(k in desc for k in explore_keywords):
        return "explore"
    # Economy
    economy_keywords = ["earn $", "spend $", "purchase all", "register "]
    if any(k in desc for k in economy_keywords):
        return "economy"
    return "other"


def forecast_case(case: dict) -> dict:
    target_x = get_x(case["target"])
    trophies = case["trophies"]
    history = case["history"]
    t_last = datetime.fromisoformat(history[-1]["at"].replace("Z", "+00:00"))

    trophy_stats = []
    
    # 1. Per-trophy stats
    for i, trophy in enumerate(trophies):
        data = []
        distinct_rates = set()
        for read in history:
            rate = read["rates"][i]
            if rate is not None:
                dt = datetime.fromisoformat(read["at"].replace("Z", "+00:00"))
                x = get_x(read["at"])
                y = logit(rate)
                w = 0.5 ** ((t_last - dt).total_seconds() / (12 * 3600))
                data.append((x, y, w, rate))
                distinct_rates.add(rate)
        
        n_eff = len(distinct_rates)
        
        if not data:
            trophy_stats.append({
                "id": trophy["id"], "class": get_class(trophy["description"]),
                "tier": trophy["tier"], "n_eff": 0, "last_rate": None
            })
            continue

        # WLS fit: y = a + b*x
        sum_w = sum(d[2] for d in data)
        xbar = sum(d[0] * d[2] for d in data) / sum_w
        ybar = sum(d[1] * d[2] for d in data) / sum_w
        
        sxx = sum(d[2] * (d[0] - xbar)**2 for d in data)
        sxy = sum(d[2] * (d[0] - xbar) * (d[1] - ybar) for d in data)
        
        b = sxy / sxx if sxx > 0 else 0.0
        
        # sigma_i
        weighted_sq_res = sum(d[2] * (d[1] - (ybar + b * (d[0] - xbar)))**2 for d in data)
        sigma = math.sqrt(weighted_sq_res / sum_w)
        sigma = max(sigma, 0.05)
        
        # anchor: last up to 3 usable reads
        anchor_data = data[-3:]
        sum_w_anchor = sum(d[2] for d in anchor_data)
        x_anchor = sum(d[0] * d[2] for d in anchor_data) / sum_w_anchor
        y_anchor = sum(d[1] * d[2] for d in anchor_data) / sum_w_anchor
        
        trophy_stats.append({
            "id": trophy["id"], "class": get_class(trophy["description"]),
            "tier": trophy["tier"], "n_eff": n_eff, "b": b, "sigma": sigma,
            "xbar": xbar, "sxx": sxx, "x_anchor": x_anchor, "y_anchor": y_anchor,
            "last_rate": data[-1][3]
        })

    # 3. Class-mean slope
    class_slopes = {}
    eligible_all = [t for t in trophy_stats if t.get("n_eff", 0) >= 3 and t["sigma"] <= 1.0]
    
    def get_weighted_mean_b(trophies_list):
        if not trophies_list: return None
        sum_wb = sum(t["b"] * t["n_eff"] / (1 + t["sigma"]**2) for t in trophies_list)
        sum_w = sum(t["n_eff"] / (1 + t["sigma"]**2) for t in trophies_list)
        return sum_wb / sum_w

    global_b_class = get_weighted_mean_b(eligible_all) or 0.0
    
    classes = set(t["class"] for t in trophy_stats)
    for c in classes:
        class_trophies = [t for t in eligible_all if t["class"] == c]
        class_slopes[c] = get_weighted_mean_b(class_trophies) or global_b_class

    # 8. Tier medians for fallback
    tier_last_rates = {}
    all_last_rates = [t["last_rate"] for t in trophy_stats if t["last_rate"] is not None]
    overall_median_rate = sorted(all_last_rates)[len(all_last_rates)//2] if all_last_rates else 1.0
    
    for tier in ["platinum", "gold", "silver", "bronze"]:
        rates = [t["last_rate"] for t in trophy_stats if t["tier"] == tier and t["last_rate"] is not None]
        tier_last_rates[tier] = sorted(rates)[len(rates)//2] if rates else overall_median_rate

    # Final forecast
    rows = []
    for t in trophy_stats:
        if t.get("n_eff", 0) == 0:
            median_logit = logit(tier_last_rates[t["tier"]])
            s = 1.50
        else:
            # 4. Shrinkage
            w_i = t["n_eff"] / (t["n_eff"] + 8)
            b_star = w_i * t["b"] + (1 - w_i) * class_slopes[t["class"]]
            
            # 5. Anchor
            median_logit = t["y_anchor"] + b_star * (target_x - t["x_anchor"])
            
            # 6. Spread
            l_i = (target_x - t["xbar"])**2 / t["sxx"] if t["sxx"] > 0 else (target_x - t["xbar"])**2
            s = math.sqrt((t["sigma"] * math.sqrt(1 + 1/t["n_eff"] + l_i))**2 + 0.30**2)
            s = max(0.30, min(2.50, s))
            if t["n_eff"] < 3:
                s = max(s, 0.80)
        
        # 7. Quantiles
        quantiles = [expit(median_logit + zi * s) for zi in Z]
        
        # Round each to 4 decimals, half-up
        rounded_q = [round4(q) for q in quantiles]
        
        # Then enforce non-decreasing and clamp to [0.01, 99.99]
        final_q = []
        last_v = -1.0 # To ensure first one can be 0.01
        for q in rounded_q:
            v = max(last_v, q)
            v_clamped = max(0.01, min(99.99, v))
            final_q.append(round4(v_clamped))
            last_v = v_clamped
            
        rows.append({"id": t["id"], "q": final_q})
        
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                case = json.load(f)
            forecast = forecast_case(case)
            out_path = OUTPUT_DIR / f"{path.stem}.out"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(forecast, f, separators=(",", ":"))
                f.write("\n")
        except Exception as e:
            # Fallback for invalid cases if needed, though spec says grader handles it.
            # We try to be robust.
            print(f"Error processing {path.name}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
