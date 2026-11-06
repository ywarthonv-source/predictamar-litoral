"""Check date clustering in the L3 coverage comparison for positive and 999 keys."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import numpy as np

from audit_candidate_chl_date_sensitivity import support_by_date
from audit_candidate_coverage import strata
from audit_ifop_artisanal import TRIP, date_or_none
from audit_ifop_zero_activity import catch_state


POSITIVE = 'reported_positive_hake'
ZERO = 'reported_no_capture_trip_code999_zero'


def audit(raw_dir, support):
    by_day = defaultdict(Counter)
    for _, _, _, rows in strata(raw_dir):
        for (_, _, end), group in rows.groupby(TRIP):
            state = catch_state(group)
            if state in (POSITIVE, ZERO):
                by_day[date_or_none(end).date()][state] += 1

    positive, zero = (sum(counts[state] for counts in by_day.values())
                      for state in (POSITIVE, ZERO))
    shared = [counts for counts in by_day.values() if counts[POSITIVE] and counts[ZERO]]
    months = defaultdict(list)
    for day, counts in sorted(by_day.items()):
        weight = counts[ZERO] / zero - counts[POSITIVE] / positive
        months[day.year, day.month].append((weight, support[day][0] >= 64))

    # Within each year-month, shuffle whole daily coverage labels across
    # sampled dates, preserving daily key counts and both capture states.
    seed, draws = 20261105, 20000
    rng = np.random.default_rng(seed)
    permuted = np.zeros(draws)
    observed = 0.0
    for values in months.values():
        weights, covered = np.asarray(values).T
        observed += weights @ covered
        labels = np.broadcast_to(covered, (draws, len(covered)))
        permuted += np.sum(rng.permuted(labels, axis=1) * weights, axis=1)
    lower_tail = int(np.count_nonzero(permuted <= observed + 1e-12))

    return {
        'positive_keys': positive, 'code999_keys': zero,
        'sampled_dates': len(by_day),
        'positive_dates': sum(c[POSITIVE] > 0 for c in by_day.values()),
        'code999_dates': sum(c[ZERO] > 0 for c in by_day.values()),
        'dates_shared': len(shared), 'code999_keys_on_shared_dates': sum(c[ZERO] for c in shared),
        'observed_coverage_difference_code999_minus_positive': float(observed),
        'permutation_mean_difference': float(permuted.mean()),
        'permutation_lower_tail_p_exploratory': (1 + lower_tail) / (1 + draws),
        'permutation_seed': seed, 'permutation_draws': draws,
        'stratification': 'year and month of recorded return date',
    }


if __name__ == '__main__':
    raw_dir, census = map(Path, sys.argv[1:])
    print(json.dumps(audit(raw_dir, support_by_date(json.loads(census.read_text()))), indent=2))
