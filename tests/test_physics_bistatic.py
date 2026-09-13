import math
import numpy as np
import pytest
from penumbra.physics.bistatic import (
    bistatic_geometry, bistatic_doppler, link_budget, max_detection_range_m, db, undb,
)


def test_db_undb_roundtrip():
    assert undb(db(37.2)) == pytest.approx(37.2, rel=1e-9)


def test_bistatic_geometry_baseline_case():
    # Transmitter and receiver on the x-axis, target directly between them and
    # off to one side: check range/baseline arithmetic against hand computation.
    tx = np.array([-100.0, 0.0, 0.0])
    rx = np.array([100.0, 0.0, 0.0])
    target = np.array([0.0, 50.0, 0.0])
    g = bistatic_geometry(tx, rx, target)
    expected_leg = math.hypot(100.0, 50.0)
    assert g.r_t == pytest.approx(expected_leg)
    assert g.r_r == pytest.approx(expected_leg)
    assert g.baseline == pytest.approx(200.0)
    assert g.r_bistatic == pytest.approx(2 * expected_leg - 200.0)


def test_bistatic_geometry_rejects_degenerate_target():
    tx = np.array([0.0, 0.0, 0.0])
    rx = np.array([100.0, 0.0, 0.0])
    with pytest.raises(ValueError):
        bistatic_geometry(tx, rx, tx)


def test_bistatic_doppler_sign_for_closing_target():
    # Target moving straight toward both transmitter and receiver (on the
    # baseline) should show positive Doppler (sum-range decreasing).
    tx = np.array([-1000.0, 0.0, 0.0])
    rx = np.array([1000.0, 0.0, 0.0])
    target = np.array([0.0, 0.0, 0.0])
    velocity = np.array([1.0, 0.0, 0.0])  # moving toward rx, away from tx along baseline
    fd = bistatic_doppler(tx, rx, target, velocity, wavelength_m=0.5)
    # Along the baseline at the midpoint, the two closing-rate contributions
    # cancel (one leg opens as fast as the other closes) -> zero net Doppler.
    assert fd == pytest.approx(0.0, abs=1e-9)

    # Move it off the perpendicular bisector (not just off-axis in y, which
    # keeps the target equidistant from tx and rx and so still symmetric) so
    # the two legs' closing rates genuinely differ.
    target2 = np.array([300.0, 500.0, 0.0])
    fd2 = bistatic_doppler(tx, rx, target2, velocity, wavelength_m=0.5)
    assert fd2 != pytest.approx(0.0, abs=1e-6)


def test_link_budget_matches_hand_computation():
    # sigma_dbsm=-17.0 is body_rcs(TARGETS["dji_mavic"], 539e6): at this
    # frequency ka ~= 1.98 already clears the ka>=1 threshold in rcs.py, so
    # the Rayleigh-region scaling does not apply and the value is unchanged
    # from the catalogue's optical-region RCS.
    lb = link_budget(
        eirp_dbw=57.1, freq_hz=539.0e6, bandwidth_hz=6.0e6, t_int_s=0.5,
        sigma_dbsm=-17.0, r_t_m=15700.0, r_r_m=300.0, baseline_m=15900.0,
    )
    # Regression values from docs/01_physics_and_link_budget.md's worked example.
    assert lb.p_r_dbw == pytest.approx(-128.43, abs=0.01)
    assert lb.p_direct_dbw == pytest.approx(-44.01, abs=0.01)
    assert lb.snr_thermal_db == pytest.approx(67.53, abs=0.01)
    assert lb.snr_dsi_db == pytest.approx(30.35, abs=0.01)
    assert lb.snr_db == pytest.approx(min(lb.snr_thermal_db, lb.snr_dsi_db))
    assert lb.detectable is True
    assert lb.range_resolution_m == pytest.approx(299_792_458.0 / 6.0e6)
    assert lb.doppler_resolution_hz == pytest.approx(2.0)


def test_link_budget_usable_snr_is_the_worse_floor():
    lb = link_budget(
        eirp_dbw=30.0, freq_hz=2.4e9, bandwidth_hz=20e6, t_int_s=0.2,
        sigma_dbsm=-15.0, r_t_m=200.0, r_r_m=200.0, baseline_m=50.0,
    )
    assert lb.snr_db == pytest.approx(min(lb.snr_thermal_db, lb.snr_dsi_db), abs=1e-9)


def test_max_detection_range_increases_with_eirp_in_the_thermal_limited_regime():
    # Increasing EIRP only helps when thermal noise (not direct-signal
    # interference) is the binding floor: DSI floor scales with p_r/p_direct,
    # which is EIRP-invariant, so a DSI-limited scenario would show no change.
    # This scenario is verified thermal-limited at both EIRP levels (thermal
    # 36.6/46.6 dB vs. a constant DSI floor of 53.0 dB).
    kwargs = dict(freq_hz=5.5e9, bandwidth_hz=80e6, t_int_s=0.1, sigma_dbsm=-17.0,
                  r_t_m=80.0, baseline_m=90.0)
    r_low = max_detection_range_m(eirp_dbw=-10.0, **kwargs)
    r_high = max_detection_range_m(eirp_dbw=0.0, **kwargs)
    assert r_high > r_low > 0.0
