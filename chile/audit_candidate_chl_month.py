"""Tabulate regional L3 support by recorded month and capture state."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from audit_candidate_chl_date_sensitivity import support_by_date
from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none
from audit_ifop_zero_activity import catch_state


def audit(raw_dir, support):
    states = ('reported_positive_hake', 'reported_no_capture_trip_code999_zero')
    months = defaultdict(Counter)
    for _, _, _, rows in strata(raw_dir):
        for (_, _, end), group in rows.groupby(TRIP):
            state = catch_state(group)
            if state in states:
                day = date_or_none(end).date()
                months[day.month][state, 'total'] += 1
                months[day.month][state, 'ge64'] += int(support[day][0] >= 64)
    p, z = states
    expected = sum(c[z, 'total'] * c[p, 'ge64'] / c[p, 'total']
                   for c in months.values() if c[z, 'total'])
    return {'months': {m: {s: {k: months[m][s, k] for k in ('total', 'ge64')}
                           for s in states} for m in sorted(months)},
            'code999_expected_ge64_using_positive_month_rates': expected}


if __name__ == '__main__':
    raw_dir, census = map(Path, sys.argv[1:])
    print(json.dumps(audit(raw_dir, support_by_date(json.loads(census.read_text()))), indent=2))

