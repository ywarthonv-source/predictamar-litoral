"""Illustrative Spearman power under independent bivariate normal draws."""
import numpy as np
from scipy.stats import rankdata

rng = np.random.default_rng(70)
for n in (8, 10, 12, 20):
    ranks = np.arange(n) - (n - 1) / 2
    norm = ranks @ ranks
    null = np.array([abs(ranks @ rng.permutation(ranks)) / norm for _ in range(100000)])
    critical = np.quantile(null, 0.95, method="higher")
    x, noise = rng.normal(size=(2, 4000, n))
    rx = rankdata(x, axis=1) - (n + 1) / 2
    powers = []
    grid = np.arange(1, 100) / 100
    for rho in grid:
        y = rho * x + np.sqrt(1 - rho**2) * noise
        ry = rankdata(y, axis=1) - (n + 1) / 2
        powers.append(np.mean(abs(np.sum(rx * ry, axis=1) / norm) > critical))
    print(n, round(critical, 4), *(round(powers[k - 1], 3) for k in (30, 50, 70)),
          next((round(r, 2) for r, power in zip(grid, powers) if power >= .8), None))
