"""Cluster-aware uncertainty over the confirmatory ladder's FA/FR rates,
clustering by `Case.instance` (the generation index) rather than treating
every case as an independent trial. Uses scripted providers so these tests
need no cache/network -- separate from `cluster_report`'s CLI, which is
exercised manually against the real committed cache (see
docs/full-technical-report.md, "Changes from v4")."""

from trust_eval.study_c.stats import clustered_bootstrap_ci, rate_statistic
from trust_eval.study_c.surrogates import scaled_cases


def test_case_instance_field_partitions_scaled_corpus_into_n_clusters():
    cases = scaled_cases(10)
    instances = {c.instance for c in cases}
    assert instances == set(range(10))
    # 4 execution + 3 authorization + 3 state per instance
    for i in range(10):
        assert sum(1 for c in cases if c.instance == i) == 10


def test_flagship_cases_and_scaled_index_zero_are_both_instance_zero():
    from trust_eval.study_c.surrogates import flagship_cases
    assert all(c.instance == 0 for c in flagship_cases())
    assert all(c.instance == 0 for c in scaled_cases(5)[:10])


def test_cluster_bootstrap_over_real_corpus_structure_is_well_formed():
    """Not a claim about any specific judge -- just that clustering the real
    40-attack corpus by instance (10 clusters of 4) produces a sane bootstrap
    CI around a known-by-construction rate."""
    cases = scaled_cases(10)
    attacks = [c for c in cases if not c.should_accept]
    assert len(attacks) == 40
    # every 3rd attack (by list position) "false-accepted", deterministic scripted signal
    is_fa = {c.task_id + c.label + str(c.instance): (i % 3 == 0) for i, c in enumerate(attacks)}
    point, lo, hi = clustered_bootstrap_ci(
        attacks, cluster_key=lambda c: str(c.instance),
        statistic=rate_statistic(lambda c: is_fa[c.task_id + c.label + str(c.instance)]))
    assert 0.0 <= lo <= point <= hi <= 1.0
