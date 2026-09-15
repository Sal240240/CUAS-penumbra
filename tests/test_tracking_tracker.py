import numpy as np
from penumbra.tracking.tracker import Tracker, Detection, TrackerConfig


def _det(t_s, pos, confidence=0.9, class_probs=None):
    return Detection(
        t_s=t_s, pos_enu_m=np.array(pos, dtype=float), pos_cov_m2=np.eye(3) * 25.0,
        confidence=confidence, class_probs=class_probs or {"drone": 0.9, "bird": 0.05, "vehicle": 0.0, "clutter": 0.05, "unknown": 0.0},
    )


def test_track_confirms_after_enough_consecutive_hits():
    tr = Tracker(TrackerConfig(confirm_m=3, confirm_n=4))
    tracks = []
    for i in range(5):
        tracks = tr.update(float(i), [_det(float(i), [i * 5.0, 0.0, 40.0])])
    assert len(tracks) == 1
    assert tracks[0].status == "confirmed"
    assert tracks[0].n_hits == 5


def test_track_is_lost_after_too_many_consecutive_misses():
    cfg = TrackerConfig(confirm_m=2, confirm_n=3, max_misses_tentative=1)
    tr = Tracker(cfg)
    tr.update(0.0, [_det(0.0, [0.0, 0.0, 40.0])])
    tr.update(1.0, [])  # miss 1 — still tentative, within budget
    tracks = tr.update(2.0, [])  # miss 2 — exceeds max_misses_tentative
    assert tracks == []


def test_two_well_separated_detections_spawn_two_tracks():
    tr = Tracker()
    tracks = tr.update(0.0, [_det(0.0, [0.0, 0.0, 40.0]), _det(0.0, [500.0, 500.0, 40.0])])
    assert len(tracks) == 2
    assert tracks[0].track_id != tracks[1].track_id


def test_class_probabilities_stay_normalized_after_updates():
    tr = Tracker()
    tracks = []
    for i in range(3):
        tracks = tr.update(float(i), [_det(float(i), [i * 2.0, 0.0, 40.0])])
    total = sum(tracks[0].class_probs.values())
    assert abs(total - 1.0) < 1e-6


def test_supporting_pairs_accumulate_across_updates():
    tr = Tracker()
    d1 = _det(0.0, [0.0, 0.0, 40.0])
    d1.pair_ids = ["atsc:N01"]
    d2 = _det(1.0, [1.0, 0.0, 40.0])
    d2.pair_ids = ["lte:N02"]
    tr.update(0.0, [d1])
    tracks = tr.update(1.0, [d2])
    assert set(tracks[0].supporting_pairs) == {"atsc:N01", "lte:N02"}
