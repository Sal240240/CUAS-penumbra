import numpy as np
from penumbra.sim.intercept import simulate_engagement, monte_carlo_pk, InterceptorConfig


def test_head_on_engagement_captures_with_small_miss_distance():
    dock = np.array([0.0, 0.0, 15.0])

    def pos_fn(t):
        return np.array([900.0 - 18.0 * t, 40.0, 60.0])

    def vel_fn(t):
        return np.array([-18.0, 0.0, 0.0])

    result = simulate_engagement(dock_pos=dock, target_pos_fn=pos_fn, target_vel_fn=vel_fn, handoff_range_m=900.0)
    assert result.captured is True
    assert result.miss_distance_m <= InterceptorConfig().net_radius_m
    assert result.seeker_acquired is True


def test_faster_crossing_target_is_not_reliably_captured():
    # Target faster than the interceptor on a beam-on crossing geometry is a
    # genuinely hard/infeasible intercept — this should not silently "succeed."
    dock = np.array([0.0, 0.0, 15.0])

    def pos_fn(t):
        return np.array([500.0, -200.0 + 35.0 * t, 50.0])

    def vel_fn(t):
        return np.array([0.0, 35.0, 0.0])

    mc = monte_carlo_pk(dock_pos=dock, target_pos_fn=pos_fn, target_vel_fn=vel_fn, handoff_range_m=600.0, n_runs=20)
    assert mc["pk"] < 0.5


def test_monte_carlo_pk_reports_consistent_run_count():
    dock = np.array([0.0, 0.0, 15.0])

    def pos_fn(t):
        return np.array([100.0 - 12.0 * t, 15.0, 40.0])

    def vel_fn(t):
        return np.array([-12.0, 0.0, 0.0])

    mc = monte_carlo_pk(dock_pos=dock, target_pos_fn=pos_fn, target_vel_fn=vel_fn, handoff_range_m=100.0, n_runs=15)
    assert mc["n_runs"] == 15
    assert 0.0 <= mc["pk"] <= 1.0
    assert 0.0 <= mc["seeker_acquire_rate"] <= 1.0


def test_engagement_result_trajectories_start_at_launch_position():
    dock = np.array([10.0, -10.0, 20.0])

    def pos_fn(t):
        return np.array([300.0, 0.0, 50.0])

    def vel_fn(t):
        return np.array([0.0, 0.0, 0.0])

    result = simulate_engagement(dock_pos=dock, target_pos_fn=pos_fn, target_vel_fn=vel_fn, handoff_range_m=300.0)
    assert np.allclose(result.interceptor_track[0], dock)
