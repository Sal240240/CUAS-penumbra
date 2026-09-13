from xml.etree import ElementTree as ET
import numpy as np
from penumbra.tracking.schema import Track
from penumbra.c2.cot import track_to_cot, cot_type


def _confirmed_drone_track() -> Track:
    return Track(
        track_id="T0042", t_s=1000.0, created_s=990.0, status="confirmed",
        pos_enu_m=np.array([50.0, 50.0, 60.0]), pos_cov_m2=np.eye(3) * 36.0,
        vel_enu_mps=np.array([12.0, -6.0, 0.0]),
        class_probs={"unknown": 0.0, "drone": 0.92, "bird": 0.02, "vehicle": 0.05, "clutter": 0.01},
        confidence=0.88, supporting_pairs=["a", "b", "c"],
    )


def test_cot_type_for_confirmed_drone():
    assert cot_type(_confirmed_drone_track()) == "a-u-A-M-H-Q"
    assert cot_type(_confirmed_drone_track(), hostile=True) == "a-h-A-M-H-Q"


def test_track_to_cot_produces_well_formed_xml():
    xml_str = track_to_cot(_confirmed_drone_track())
    root = ET.fromstring(xml_str)  # raises if malformed
    assert root.tag == "event"
    assert root.attrib["type"] == "a-u-A-M-H-Q"
    point = root.find("point")
    assert point is not None
    assert float(point.attrib["ce"]) > 0.0


def test_cot_carries_evidence_and_class_probabilities():
    xml_str = track_to_cot(_confirmed_drone_track())
    root = ET.fromstring(xml_str)
    penumbra_detail = root.find("./detail/__penumbra")
    assert penumbra_detail is not None
    assert penumbra_detail.attrib["status"] == "confirmed"
    classes = {c.attrib["name"]: float(c.attrib["p"]) for c in penumbra_detail.findall("class")}
    assert classes["drone"] == 0.92
