import pytest

from selfspec_calculator.stats import (
    SpeculationStats,
    expected_committed_tokens_per_burst,
    expected_wasted_verifier_steps,
    normalize_histogram,
    verifier_steps_per_burst,
)


def test_normalize_histogram() -> None:
    out = normalize_histogram({0: 2.0, 1: 2.0})
    assert out == {0: 0.5, 1: 0.5}


def test_expected_committed_tokens_per_burst() -> None:
    stats = SpeculationStats(k=2, histogram={0: 0.5, 2: 0.5})
    # E[a+1] = 0.5*(0+1) + 0.5*(2+1) = 2
    assert expected_committed_tokens_per_burst(stats) == pytest.approx(2.0)


def test_expected_wasted_verifier_steps() -> None:
    stats = SpeculationStats(k=4, histogram={0: 1.0})
    # always mismatch at first token -> wasted verifier steps = K-a = 4
    assert expected_wasted_verifier_steps(stats) == pytest.approx(4.0)


def test_verifier_steps_per_burst() -> None:
    stats = SpeculationStats(k=7, histogram={7: 1.0})
    assert verifier_steps_per_burst(stats) == 8


def test_histogram_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        SpeculationStats(k=2, histogram={3: 1.0})

