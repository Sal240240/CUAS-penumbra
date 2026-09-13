from penumbra.reasoning.evidence import Observation, build_ledger, combine


def test_confident_hovering_drone_scenario():
    obs = Observation(
        flash_hz=216, tip_doppler_hz=1700, band_freq_hz=3.5e9, n_pairs=5, n_bands=3,
        nis_sigma=1.2, hover_s=4.5, max_speed_mps=18, max_accel_mps2=3,
        alt_agl_m=61, alt_sigma_m=8, on_street_axis=False, persistence_s=6.0,
    )
    ledger = build_ledger(obs)
    probs = combine(ledger)
    assert probs["drone"] == max(probs.values())
    assert probs["drone"] > 0.85


def test_bird_wingbeat_scenario_favors_bird_over_drone():
    obs = Observation(flash_hz=4.2, wingbeat_hz=4.2, n_pairs=4, n_bands=2, nis_sigma=1.5,
                       hover_s=0.0, max_speed_mps=12, max_accel_mps2=1.5, alt_agl_m=45,
                       alt_sigma_m=12, on_street_axis=False, persistence_s=8.0)
    ledger = build_ledger(obs)
    probs = combine(ledger)
    assert probs["bird"] > probs["drone"]


def test_ground_vehicle_scenario_favors_vehicle():
    # n_pairs must be >= 3 for solid multistatic corroboration (+"real"-axis
    # evidence); with only 1-2 pairs the "real" axis stays too close to its
    # 0.5 prior for anything to confidently beat "clutter" — that is the
    # evidence ledger correctly refusing to overclaim on weak coverage, not
    # a bug, but it means this test needs a properly corroborated scenario.
    obs = Observation(n_pairs=4, n_bands=2, nis_sigma=1.0, hover_s=0.0, max_speed_mps=14,
                       max_accel_mps2=2, alt_agl_m=1.0, alt_sigma_m=2.0, on_street_axis=True,
                       persistence_s=5.0)
    ledger = build_ledger(obs)
    probs = combine(ledger)
    assert probs["vehicle"] == max(probs.values())


def test_weak_evidence_scenario_does_not_overclaim_drone():
    obs = Observation(n_pairs=2, n_bands=1, nis_sigma=3.4, hover_s=0.0, max_speed_mps=6,
                       max_accel_mps2=1, on_street_axis=False, persistence_s=1.2)
    ledger = build_ledger(obs)
    probs = combine(ledger)
    assert probs["drone"] < 0.5


def test_class_probabilities_sum_to_one():
    obs = Observation(n_pairs=3, n_bands=2, hover_s=1.0, max_speed_mps=10, max_accel_mps2=2,
                       on_street_axis=False, persistence_s=2.0)
    probs = combine(build_ledger(obs))
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_external_rf_corroboration_increases_drone_probability():
    base = Observation(n_pairs=3, n_bands=2, hover_s=1.0, max_speed_mps=10, max_accel_mps2=2,
                        on_street_axis=False, persistence_s=2.0)
    corroborated = Observation(**{**base.__dict__, "external_rf_detect": True})
    p_base = combine(build_ledger(base))["drone"]
    p_corroborated = combine(build_ledger(corroborated))["drone"]
    assert p_corroborated > p_base
