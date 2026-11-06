"""Audit a private Sernapesca SAIP ZIP. Print only aggregate evidence."""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from openpyxl import load_workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    with ZipFile(args.archive) as archive:
        workbook_bytes = archive.read("Informacion SAIP.xlsx")
    print("sha256 ZIP/XLSX", sha256(args.archive.read_bytes()).hexdigest(),
          sha256(workbook_bytes).hexdigest())
    book = load_workbook(BytesIO(workbook_bytes), read_only=True, data_only=True)
    land, zero = ([row for row in book[sheet].iter_rows(min_row=7, values_only=True)
                   if row[1]] for sheet in ("Desembarque", "Viajes sin pesca"))
    for rows in (land, zero):
        print("coverage", len(rows), [
            (min(dates).date(), max(dates).date(),
             sum(t.time() != datetime.min.time() for t in dates), len(rows) - len(dates))
            for dates in ([r[i] for r in rows if isinstance(r[i], datetime)] for i in (6, 7))
        ])
    port = [r for r in land if r[3] == "Portales"]
    hake = [r for r in port if r[9] == "Merluza Comun"]
    def key(row):
        return row[4], row[6], row[7]

    def month(row):
        return row[7].strftime("%Y-%m")

    weights = sorted((Decimal(str(r[13])) for r in hake), reverse=True)
    print("hake rows/keys/boats/arrival days/same dates", len(hake),
          len({key(r) for r in hake}), len({r[4] for r in hake}),
          len({r[7] for r in hake}), sum(r[6] == r[7] for r in hake))
    print("zones", sorted(Counter(r[12] for r in hake).items()))
    print("rows and candidate keys by month and gear", [
        (group, len(rows), len({key(r) for r in rows}))
        for group in sorted({(month(r), r[11]) for r in hake})
        for rows in [[r for r in hake if (month(r), r[11]) == group]]
    ])
    print("weights total/without max/max/second/zero",
          sum(weights), sum(weights[1:]), *weights[:2], weights.count(0))
    print("September non-hake", sum(r[7].month == 9 for r in port if r not in hake))
    print("no-fishing rows by arrival year", sorted(Counter(
        r[7].year for r in zero if r[3] == "Portales").items()))
    gears = {"Enmalle", "Espinel"}
    eligible = {key(r) for r in port if r[11] in gears}
    target = {key(r) for r in hake if r[11] in gears}
    print("candidate landing keys / no hake in either gear", len(eligible),
          len(eligible - target))
    z = ZoneInfo("America/Santiago")
    counts = Counter()
    for i in range(731):
        day = date(2024, 1, 1) + timedelta(days=i)
        if day.month in (4, 9):
            offset = datetime(day.year, day.month, day.day, 20, tzinfo=z).utcoffset()
            counts[(day.year, day.month, int(offset.total_seconds() / 3600))] += 1
    print("offset at 20:00 in transition months", sorted(counts.items()))


if __name__ == "__main__":
    main()
