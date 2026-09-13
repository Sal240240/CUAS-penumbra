import pytest
from penumbra.physics.rcs import body_rcs, blade_rcs, TARGETS


def test_body_rcs_equals_optical_value_at_high_frequency():
    # At a high enough frequency the target is deep in the optical region
    # (ka >> 1), so body_rcs should return the catalogue value unmodified.
    tg = TARGETS["dji_mavic"]
    rcs = body_rcs(tg, freq_hz=50e9)
    assert rcs == pytest.approx(tg.rcs_opt_dbsm, abs=1e-6)


def test_body_rcs_drops_in_rayleigh_region():
    # At very low frequency (ka << 1) the Rayleigh (ka)^4 scaling should pull
    # the RCS well below the optical-region value.
    tg = TARGETS["dji_mavic"]
    rcs_low = body_rcs(tg, freq_hz=100e6)
    rcs_high = body_rcs(tg, freq_hz=50e9)
    assert rcs_low < rcs_high


def test_body_rcs_monotonic_with_frequency_below_resonance():
    tg = TARGETS["dji_mini"]
    freqs = [50e6, 100e6, 200e6, 400e6]
    values = [body_rcs(tg, f) for f in freqs]
    assert values == sorted(values)


def test_blade_rcs_below_body_rcs_at_same_frequency():
    tg = TARGETS["m30"]  # carbon blades
    freq = 3.5e9
    assert blade_rcs(tg, freq) < body_rcs(tg, freq)


def test_blade_rcs_zero_blades_returns_floor():
    bird = TARGETS["bird_gull"]
    assert blade_rcs(bird, 1e9) == -80.0


def test_plastic_blades_weaker_than_carbon_at_same_geometry():
    # Two targets differing only in blade material, everything else equal.
    from dataclasses import replace
    carbon = TARGETS["m30"]
    plastic = replace(carbon, blade_material="plastic")
    freq = 3.5e9
    assert blade_rcs(plastic, freq) < blade_rcs(carbon, freq)
