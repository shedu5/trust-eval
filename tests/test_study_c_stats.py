"""Statistics layer: Wilson/exact binomial CIs, exact McNemar, clustered
bootstrap. Checked against known closed-form values, not against scipy (there
is no scipy dependency in this project by design)."""

import math

from trust_eval.study_c.stats import (
    clopper_pearson_ci,
    clustered_bootstrap_ci,
    mcnemar_exact,
    rate_statistic,
    wilson_ci,
)


def test_wilson_ci_zero_n_is_full_range():
    assert wilson_ci(0, 0) == (0.0, 1.0)


def test_wilson_ci_contains_point_estimate():
    lo, hi = wilson_ci(1, 4)
    assert lo < 0.25 < hi


def test_wilson_ci_zero_successes_has_positive_upper_bound():
    # 0/4 does NOT mean the true rate is provably 0 -- the interval must say so.
    lo, hi = wilson_ci(0, 4)
    assert lo == 0.0
    assert hi > 0.0


def test_clopper_pearson_matches_wilson_at_large_n():
    # at large n the two intervals should nearly coincide
    w_lo, w_hi = wilson_ci(500, 1000)
    c_lo, c_hi = clopper_pearson_ci(500, 1000)
    assert abs(w_lo - c_lo) < 0.01
    assert abs(w_hi - c_hi) < 0.01


def test_clopper_pearson_is_wider_than_wilson_at_small_n():
    # exact CIs guarantee >= nominal coverage and are conservative (wider) at
    # small n -- this is the whole reason to report both.
    w_lo, w_hi = wilson_ci(1, 4)
    c_lo, c_hi = clopper_pearson_ci(1, 4)
    assert c_hi - c_lo >= w_hi - w_lo - 1e-9


def test_clopper_pearson_edge_cases():
    assert clopper_pearson_ci(0, 5)[0] == 0.0
    assert clopper_pearson_ci(5, 5)[1] == 1.0
    lo, hi = clopper_pearson_ci(0, 5)
    assert 0.0 <= lo <= hi <= 1.0


def test_clopper_pearson_zero_n():
    assert clopper_pearson_ci(0, 0) == (0.0, 1.0)


def test_mcnemar_exact_no_discordant_pairs_is_certain():
    assert mcnemar_exact(0, 0) == 1.0


def test_mcnemar_exact_symmetric_discordance_is_high_p():
    # b == c: no evidence of a systematic difference
    assert mcnemar_exact(5, 5) > 0.5


def test_mcnemar_exact_lopsided_discordance_is_significant():
    # 0 vs 10 discordant pairs: essentially certain the two protocols differ
    assert mcnemar_exact(0, 10) < 0.01


def test_mcnemar_exact_matches_binomial_two_sided_by_hand():
    # b=1, c=9 (n=10): two-sided p = 2 * P(X<=1) for X~Binomial(10, 0.5)
    n, k = 10, 1
    tail = sum(math.comb(n, i) for i in range(0, k + 1))
    expected = min(1.0, 2 * tail / (2 ** n))
    assert abs(mcnemar_exact(1, 9) - expected) < 1e-9


def test_clustered_bootstrap_point_matches_plain_rate():
    items = [("a", True), ("a", False), ("b", True), ("b", True)]
    stat = rate_statistic(lambda it: it[1])
    point, lo, hi = clustered_bootstrap_ci(items, cluster_key=lambda it: it[0], statistic=stat,
                                           n_resamples=500, seed=1)
    assert point == 0.75
    assert 0.0 <= lo <= point <= hi <= 1.0


def test_clustered_bootstrap_all_true_is_degenerate_at_one():
    items = [("a", True), ("a", True), ("b", True)]
    stat = rate_statistic(lambda it: it[1])
    point, lo, hi = clustered_bootstrap_ci(items, cluster_key=lambda it: it[0], statistic=stat,
                                           n_resamples=200, seed=2)
    assert point == lo == hi == 1.0


def test_clustered_bootstrap_no_clusters_returns_point_only():
    stat = rate_statistic(lambda it: it[1])
    point, lo, hi = clustered_bootstrap_ci([], cluster_key=lambda it: it[0], statistic=stat)
    assert point == lo == hi == 0.0
