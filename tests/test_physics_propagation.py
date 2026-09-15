import pytest
from penumbra.physics.propagation import (
    Box, knife_edge_loss_db, fresnel_nu, path_obstruction, segment_intersects_box, MAX_EXCESS_LOSS_DB,
)


def test_knife_edge_loss_zero_for_clear_line_of_sight():
    # nu <= -0.78 is the clear-line-of-sight region per ITU-R P.526-15 eq. 31.
    assert knife_edge_loss_db(-1.0) == 0.0
    assert knife_edge_loss_db(-0.78) == 0.0


def test_knife_edge_loss_increases_with_obstruction_height():
    losses = [knife_edge_loss_db(nu) for nu in (0.0, 0.5, 1.0, 2.0)]
    assert losses == sorted(losses)


def test_fresnel_nu_zero_height_gives_zero():
    assert fresnel_nu(0.0, 100.0, 100.0, 0.5) == 0.0


def test_path_obstruction_no_buildings_is_free_space():
    p = (0.0, 0.0, 40.0)
    q = (500.0, 0.0, 40.0)
    loss, n = path_obstruction(p, q, [], wavelength_m=0.5)
    assert loss == 0.0
    assert n == 0


def test_path_obstruction_tall_building_in_the_way():
    p = (0.0, 0.0, 40.0)
    q = (500.0, 0.0, 40.0)
    tall_building = Box(x0=200.0, y0=-20.0, x1=250.0, y1=20.0, height=80.0)
    loss, n = path_obstruction(p, q, [tall_building], wavelength_m=0.5)
    assert loss > 0.0
    assert n == 1
    assert loss <= MAX_EXCESS_LOSS_DB


def test_path_obstruction_capped_at_max_excess_loss():
    p = (0.0, 0.0, 0.0)
    q = (500.0, 0.0, 0.0)
    very_tall = Box(x0=200.0, y0=-20.0, x1=250.0, y1=20.0, height=500.0)
    loss, _ = path_obstruction(p, q, [very_tall], wavelength_m=0.1)
    assert loss == MAX_EXCESS_LOSS_DB


def test_segment_intersects_box_true_when_path_clips_volume():
    b = Box(x0=10.0, y0=-10.0, x1=20.0, y1=10.0, height=50.0)
    # bool(...) rather than `is True`: the function returns a numpy bool
    # scalar, which is equal but not identical to the Python singleton.
    assert bool(segment_intersects_box((0.0, 0.0, 10.0), (30.0, 0.0, 10.0), b)) is True
    assert bool(segment_intersects_box((0.0, 0.0, 60.0), (30.0, 0.0, 60.0), b)) is False
