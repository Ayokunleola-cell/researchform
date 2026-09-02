# backend/analysis/engine/bootstrap.py
"""
Shared bootstrap utility for ResearchForm statistical engine.

Provides publication-grade bootstrapped confidence intervals using
the Bias-Corrected and Accelerated (BCa) method — the gold standard
used by SPSS PROCESS macro (Hayes, 2022).

Usage:
    from analysis.engine.bootstrap import bootstrap_ci, bootstrap_mean_diff, bootstrap_r

All functions are NumPy-based and fast enough for n=5,000 with 2,000 resamples.
"""
from __future__ import annotations
import numpy as np
from scipy import stats as _stats
from typing import Callable, Tuple, Optional


# ── Core BCa Bootstrap ────────────────────────────────────────────────────────

def bootstrap_ci(
    statistic_fn: Callable,
    data: np.ndarray,
    n_resamples: int = 2000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Tuple[Optional[float], Optional[float], float]:
    """
    Bias-Corrected and Accelerated (BCa) bootstrap CI for a univariate statistic.

    Args:
        statistic_fn: Function that takes a 1D array and returns a scalar.
        data:         1D numpy array of observed values.
        n_resamples:  Number of bootstrap resamples (default 2000).
        ci_level:     Confidence level (default 0.95).
        random_state: Random seed for reproducibility.

    Returns:
        (ci_lower, ci_upper, observed_statistic)
    """
    rng = np.random.default_rng(random_state)
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 3:
        return None, None, float(statistic_fn(data))

    observed = float(statistic_fn(data))

    # Generate bootstrap distribution
    boot_stats = np.array([
        statistic_fn(rng.choice(data, size=n, replace=True))
        for _ in range(n_resamples)
    ])

    return _bca_interval(observed, boot_stats, data, statistic_fn, ci_level)


def bootstrap_ci_two_sample(
    statistic_fn: Callable,
    x: np.ndarray,
    y: np.ndarray,
    n_resamples: int = 2000,
    ci_level: float = 0.95,
    random_state: int = 42,
) -> Tuple[Optional[float], Optional[float], float]:
    """
    BCa bootstrap CI for a two-sample statistic (e.g., mean difference, Cohen's d).

    statistic_fn receives (x_resample, y_resample) and returns a scalar.
    """
    rng = np.random.default_rng(random_state)
    x = np.asarray(x, dtype=float); x = x[~np.isnan(x)]
    y = np.asarray(y, dtype=float); y = y[~np.isnan(y)]
    if len(x) < 2 or len(y) < 2:
        return None, None, float(statistic_fn(x, y))

    observed = float(statistic_fn(x, y))

    boot_stats = np.array([
        statistic_fn(
            rng.choice(x, size=len(x), replace=True),
            rng.choice(y, size=len(y), replace=True),
        )
        for _ in range(n_resamples)
    ])

    # Use percentile CI for two-sample (BCa jackknife is expensive for two samples)
    alpha = 1 - ci_level
    ci_l = float(np.percentile(boot_stats, 100 * alpha / 2))
    ci_u = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
    return ci_l, ci_u, observed


# ── BCa Internal ──────────────────────────────────────────────────────────────

def _bca_interval(
    observed: float,
    boot_stats: np.ndarray,
    data: np.ndarray,
    statistic_fn: Callable,
    ci_level: float,
) -> Tuple[float, float, float]:
    """Compute BCa-corrected interval from bootstrap distribution."""
    alpha = 1 - ci_level
    n = len(data)

    # Bias correction factor z0
    prop_less = np.mean(boot_stats < observed)
    prop_less = np.clip(prop_less, 1e-6, 1 - 1e-6)
    z0 = float(_stats.norm.ppf(prop_less))

    # Acceleration factor a via jackknife
    jack_stats = np.array([
        statistic_fn(np.delete(data, i))
        for i in range(min(n, 200))   # cap jackknife at 200 for speed
    ])
    jack_mean = np.mean(jack_stats)
    num   = np.sum((jack_mean - jack_stats) ** 3)
    denom = 6 * (np.sum((jack_mean - jack_stats) ** 2) ** 1.5)
    a = float(num / denom) if denom != 0 else 0.0

    # Adjusted quantiles
    z_alpha_lo = _stats.norm.ppf(alpha / 2)
    z_alpha_hi = _stats.norm.ppf(1 - alpha / 2)

    def _adj_q(z_a):
        num_z = z0 + z_a
        return float(_stats.norm.cdf(z0 + num_z / (1 - a * num_z)))

    q_lo = np.clip(_adj_q(z_alpha_lo), 0.001, 0.999)
    q_hi = np.clip(_adj_q(z_alpha_hi), 0.001, 0.999)

    ci_l = float(np.percentile(boot_stats, 100 * q_lo))
    ci_u = float(np.percentile(boot_stats, 100 * q_hi))
    return ci_l, ci_u, observed


# ── Convenience wrappers ──────────────────────────────────────────────────────

def bootstrap_mean(data, n_resamples=2000, ci_level=0.95, random_state=42):
    """Bootstrap CI for a sample mean."""
    return bootstrap_ci(np.mean, data, n_resamples, ci_level, random_state)


def bootstrap_mean_diff(x, y, n_resamples=2000, ci_level=0.95, random_state=42):
    """Bootstrap CI for the difference in means (x - y), e.g., for t-tests."""
    fn = lambda a, b: np.mean(a) - np.mean(b)
    return bootstrap_ci_two_sample(fn, x, y, n_resamples, ci_level, random_state)


def bootstrap_cohens_d(x, y, n_resamples=2000, ci_level=0.95, random_state=42):
    """Bootstrap CI for Cohen's d."""
    def _d(a, b):
        pooled = np.sqrt(((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1)) / (len(a) + len(b) - 2))
        return (np.mean(a) - np.mean(b)) / pooled if pooled > 0 else 0.0
    return bootstrap_ci_two_sample(_d, x, y, n_resamples, ci_level, random_state)


def bootstrap_r(x, y, n_resamples=2000, ci_level=0.95, random_state=42):
    """Bootstrap CI for Pearson or Spearman correlation."""
    from scipy.stats import pearsonr
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    if len(x) < 4:
        return None, None, float(pearsonr(x, y)[0]) if len(x) >= 2 else None

    observed = float(pearsonr(x, y)[0])
    rng = np.random.default_rng(random_state)
    n = len(x)
    idx = np.arange(n)

    boot_stats = np.array([
        pearsonr(x[i := rng.choice(idx, size=n, replace=True)], y[i])[0]
        for _ in range(n_resamples)
    ])

    return _bca_interval(observed, boot_stats, x, lambda a: pearsonr(a, y[:len(a)])[0], ci_level)


def bootstrap_paired_diff(pre, post, n_resamples=2000, ci_level=0.95, random_state=42):
    """Bootstrap CI for paired mean difference (post - pre)."""
    pre  = np.asarray(pre, dtype=float)
    post = np.asarray(post, dtype=float)
    diff = post - pre
    mask = ~np.isnan(diff)
    return bootstrap_ci(np.mean, diff[mask], n_resamples, ci_level, random_state)


def n_resamples_for(n: int) -> int:
    """
    Adaptively choose number of resamples based on sample size.
    Smaller samples need more resamples for stable tail estimates.
    """
    if n < 30:   return 5000
    if n < 100:  return 3000
    if n < 500:  return 2000
    return 1000
