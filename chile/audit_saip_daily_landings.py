"""Describe matched daily landings without publishing row-level data."""
import argparse
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
import numpy as np
from scipy.stats import rankdata, spearmanr

MIN_DAYS = 8
ZIP_SHA = "556cfcc9c0f068e10d5c3d972bbd224082d7e4c427498904c687c48d35cd06ba"


def correlation(x, y):
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return round(float(spearmanr(x, y).statistic), 4)


def permutation_p(x, y, permutations):
    x, y = rankdata(x), rankdata(y)
    x -= x.mean()
    y -= y.mean()
    observed = abs(x @ y)
    simulated = abs(np.einsum("ij,j->i", y[permutations], x))
    return float((1 + np.count_nonzero(simulated >= observed - 1e-10))
                 / (1 + len(permutations)))


def audit(archive_path, environment_path, *, iid_diagnostic=False):
    my, nrt = json.loads(environment_path.read_text())
    raw = archive_path.read_bytes()
    if sha256(raw).hexdigest() != ZIP_SHA:
        raise ValueError("Unexpected SAIP archive")
    with ZipFile(BytesIO(raw)) as archive:
        book = load_workbook(BytesIO(archive.read("Informacion SAIP.xlsx")),
                             read_only=True, data_only=True)
    groups = defaultdict(lambda: defaultdict(list))
    dates = []
    recovered = 0
    november = 0
    for row in book["Desembarque"].iter_rows(min_row=7, values_only=True):
        if row[3] != "Portales" or row[9] != "Merluza Comun" or row[11] not in {"Enmalle", "Espinel"}:
            continue
        day = row[7].date().isoformat()
        if not "2026-01-01" <= day <= "2026-11-03":
            raise ValueError("Recalada outside requested window")
        dates.append(day)
        if day >= "2026-11-01":
            november += 1
        if day not in my["chl"] and nrt["chl"].get(day) is not None:
            recovered += 1
        daily = groups[day[:7], row[11]]
        if my["chl"].get(day) is not None:
            if float(row[13]) == 84.904:
                raise ValueError("Anomaly unexpectedly matched; review sensitivity")
            daily[day].append(float(row[13]) * 1000)
    strata = []
    rng = np.random.default_rng(70)
    for (month, gear), daily in sorted(groups.items()):
        days = sorted(daily)
        result = {"month": month, "gear": gear, "days": len(days)}
        if len(days) >= MIN_DAYS:
            chl = [my["chl"][day] for day in days]
            weights = [sum(daily[day]) for day in days]
            counts = [len(daily[day]) for day in days]
            result.update(rho_daily_kg=correlation(chl, weights),
                          rho_mean_kg_per_row=correlation(chl, [w/n for w,n in zip(weights,counts)]),
                          rho_daily_row_count=correlation(chl, counts))
            if iid_diagnostic:
                permutations = np.array([rng.permutation(len(days)) for _ in range(40000)])
                measures = (weights, [w/n for w,n in zip(weights,counts)], counts)
                result["iid_permutation_diagnostic"] = [
                    permutation_p(chl, values, permutations)
                    if len(set(chl)) > 1 and len(set(values)) > 1 else None
                    for values in measures
                ]
        strata.append(result)
    early = lambda day: day[:7] <= "2026-04"
    matched = [day for day in dates if my["chl"].get(day) is not None]
    return {"minimum_days": MIN_DAYS, "rows": len(dates), "matched_rows": len(matched),
            "jan_apr_rows": sum(map(early, dates)), "jan_apr_matched_rows": sum(map(early, matched)),
            "november_rows_through_day_3": november, "nrt_finite_rows_outside_my": recovered,
            "strata": strata}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("environment", type=Path)
    parser.add_argument('--iid-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.archive, args.environment, iid_diagnostic=args.iid_diagnostic), indent=2, allow_nan=False))
