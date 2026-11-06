"""Count support by month and gear without publishing individual records."""
import argparse
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook


def audit(zip_path, environment_path):
    my, nrt = json.loads(environment_path.read_text())
    if my["cell"] != nrt["cell"] or my["units"] != nrt["units"]:
        raise ValueError("Environmental products use different cells or units")
    a, b = my["chl"], nrt["chl"]
    common = a.keys() & b.keys()
    paired = [d for d in common if a[d] is not None and b[d] is not None]
    raw = zip_path.read_bytes()
    if sha256(raw).hexdigest() != (
        "556cfcc9c0f068e10d5c3d972bbd224082d7e4c427498904c687c48d35cd06ba"
    ):
        raise ValueError("Unexpected SAIP archive")
    with ZipFile(BytesIO(raw)) as archive:
        book = load_workbook(BytesIO(archive.read("Informacion SAIP.xlsx")),
                             read_only=True, data_only=True)
    groups = defaultdict(list)
    for row in book["Desembarque"].iter_rows(min_row=7, values_only=True):
        if row[3] == "Portales" and row[9] == "Merluza Comun" and row[11] in {"Enmalle", "Espinel"}:
            day = row[7].date().isoformat()
            groups[day[:7], row[11]].append((day, Decimal(str(row[13]))))
    strata = []
    for (month, gear), rows in sorted(groups.items()):
        days = {day for day, _ in rows}
        finite = {day for day in days if a.get(day) is not None}
        outside = days - a.keys()
        linked = [weight for day, weight in rows if day in finite]
        clean = [weight for weight in linked if weight != Decimal("84.904")]
        strata.append({"month": month, "gear": gear, "rows": len(rows),
                       "days": len(days), "finite_days": len(finite),
                       "finite_rows": len(linked), "outside_days": len(outside),
                       "outside_rows": sum(day in outside for day, _ in rows),
                       "matched_t_original": str(round(sum(linked, Decimal(0)), 3)),
                       "matched_t_without_anomaly": str(round(sum(clean, Decimal(0)), 3)),
                       "anomaly_linked": len(linked) - len(clean)})
    return {"overlap_days": len(common), "paired_finite": len(paired),
            "paired_identical": sum(a[d] == b[d] for d in paired),
            "strata": strata}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("environment", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive, args.environment), indent=2))
