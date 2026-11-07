"""Audit daily chlorophyll support under three recorded-date scenarios."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
import sys

from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none
from audit_ifop_zero_activity import catch_state


def support_by_date(census):
    counts = census['daily_finite_counts']
    start = date.fromisoformat(counts['first_date'])
    stop = date.fromisoformat(counts['last_date'])
    l3, l4 = counts['l3_finite_in_bounds'], counts['l4_finite_in_bounds']
    if counts['step_days'] != 1 or len(l3) != len(l4) or len(l3) != (stop-start).days + 1:
        raise ValueError('Unexpected daily census axis')
    return {start + timedelta(days=i): (a, b) for i, (a, b) in enumerate(zip(l3, l4))}


def audit(raw_dir, support):
    for year, gear, _, rows in strata(raw_dir):
        if rows[TRIP].eq('').any(axis=None):
            raise ValueError('Unexpected missing candidate key')
        offsets = Counter()
        windows = Counter()
        pair = Counter()
        calendar = Counter()
        by_state = defaultdict(Counter)
        for (_, departure_raw, return_raw), group in rows.groupby(TRIP):
            departure, recorded = map(date_or_none, (departure_raw, return_raw))
            if departure is None or recorded is None or departure > recorded:
                raise ValueError('Unexpected candidate interval')
            for shift in (0, 3, 4):
                for label, timestamp in [('departure', departure), ('return', recorded)]:
                    calendar[shift, label] += int(
                        (timestamp + timedelta(hours=shift)).date() != timestamp.date())
            days = [recorded.date() + timedelta(days=i) for i in (-1, 0, 1)]
            values = [support.get(day) for day in days]
            state = by_state[catch_state(group)]
            state['keys'] += 1
            if values[0] is not None and values[1] is not None:
                before, center = (value[0] >= 64 for value in values[:2])
                pair['both' if before and center else 'mixed' if before or center else 'neither'] += 1
                state['ge64_center'] += int(center)
                state['ge64_changes'] += int(before != center)
            else:
                pair['incomplete'] += 1
            for offset, value in zip((-1, 0, 1), values):
                if value is None:
                    offsets[offset, 'outside_axis'] += 1
                else:
                    offsets[offset, 'L3_any'] += int(value[0] > 0)
                    offsets[offset, 'L3_ge64'] += int(value[0] >= 64)
                    offsets[offset, 'L4_any'] += int(value[1] > 0)
            if any(value is None for value in values):
                windows['incomplete_axis'] += 1
                continue
            available = [value[0] > 0 for value in values]
            windows['L3_all_three'] += int(all(available))
            windows['L3_none_of_three'] += int(not any(available))
            windows['L3_mixed_three'] += int(any(available) and not all(available))
            windows['L3_center_missing_neighbor_available'] += int(
                not available[1] and (available[0] or available[2]))
            dense = [value[0] >= 64 for value in values]
            windows['L3_ge64_all_three'] += int(all(dense))
            windows['L3_ge64_none_of_three'] += int(not any(dense))
            windows['L3_ge64_mixed_three'] += int(any(dense) and not all(dense))
            windows['L4_all_three'] += int(all(value[1] > 0 for value in values))
        print(year, gear, sum(state["keys"] for state in by_state.values()), {i: {k: offsets[i, k] for k in
              ('outside_axis', 'L3_any', 'L3_ge64', 'L4_any')} for i in (-1, 0, 1)}, dict(windows))
        print("two-day threshold", dict(pair), "endpoint changes", dict(calendar))
        print("catch states", {name: dict(counts) for name, counts in sorted(by_state.items())})


if __name__ == '__main__':
    raw_dir, census_path = map(Path, sys.argv[1:])
    audit(raw_dir, support_by_date(json.loads(census_path.read_text())))


