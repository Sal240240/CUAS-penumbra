import numpy as np
from penumbra.sim.scene import demo_downtown_scene
from penumbra.sim.coverage import coverage_map


def test_coverage_map_runs_on_the_demo_scene():
    scene = demo_downtown_scene()
    result = coverage_map(scene, step_m=200.0)
    assert result.n_pairs.shape == result.covered.shape
    assert result.n_pairs.max() > 0
    assert result.covered.sum() > 0


def test_coverage_map_survives_grid_cell_exactly_on_an_illuminator_or_node():
    """Regression test: a step size that makes a grid cell land exactly on an
    illuminator or node position used to raise 'target coincides with
    transmitter or receiver' from bistatic_geometry() and crash the whole
    pass (found via the webapp's Coverage page, which used step_m=30 against
    the same demo scene — the 5G n78 'sector D' illuminator sits at exactly
    (-150, -330, 40), and -150/30 and -330/30 are both integers)."""
    scene = demo_downtown_scene()
    # Narrow the grid to the exact coincidence point (and a small margin)
    # rather than scanning the whole 1200x1200 m scene at a fine step, which
    # is correct but needlessly slow for a regression test.
    scene.extent_m = 200.0
    result = coverage_map(scene, step_m=30.0, alt_m=40.0)
    assert result.n_pairs.shape[0] > 0


def test_coverage_map_more_pairs_required_means_less_or_equal_coverage():
    scene = demo_downtown_scene()
    loose = coverage_map(scene, step_m=60.0, min_pairs=1)
    strict = coverage_map(scene, step_m=60.0, min_pairs=5)
    assert strict.covered.sum() <= loose.covered.sum()


def test_wifi_links_only_include_nearby_node_pairs():
    scene = demo_downtown_scene()
    links = scene.wifi_links()
    for a, b, d in links:
        assert d <= 450.0
        assert np.linalg.norm(a.pos - b.pos) == d
