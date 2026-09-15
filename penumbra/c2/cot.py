"""Cursor-on-Target (CoT) adapter.

CoT event schema per MITRE "Cursor-on-Target Message Router User's Guide" and
the ATAK CoT conventions. Type codes use the MIL-STD-2525 mapping:
  a-h-A-M-H-Q   hostile / air / military / rotary-wing / drone  (multirotor UAS)
  a-u-A-M-H-Q   unknown-affiliation multirotor UAS
  a-n-A         neutral air (bird)
  a-u-G-E-V     unknown ground vehicle
Uncertainty is carried in the standard `ce` (circular error, m) and `le`
(linear/vertical error, m) attributes; velocity in <track speed course/>;
PENUMBRA-specific evidence goes in a namespaced <__penumbra> detail element that
TAK clients ignore harmlessly.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
import math
import numpy as np
from ..tracking.schema import Track
from .geodesy import enu_to_geodetic


def cot_type(track: Track, hostile: bool = False) -> str:
    c = track.top_class
    if c == "drone":
        return "a-h-A-M-H-Q" if hostile else "a-u-A-M-H-Q"
    if c == "bird":
        return "a-n-A"
    if c == "vehicle":
        return "a-u-G-E-V"
    return "a-u-A"


def track_to_cot(track: Track, *, now: datetime | None = None, stale_s: float = 10.0,
                 ref=None, hostile: bool = False, sensor_uid: str = "PENUMBRA-FABRIC-01") -> str:
    now = now or datetime.now(timezone.utc)
    lat, lon, hae = enu_to_geodetic(track.pos_enu_m, ref) if ref else enu_to_geodetic(track.pos_enu_m)
    ce = float(math.sqrt(max(np.trace(track.pos_cov_m2[:2, :2]) / 2.0, 1e-6)))
    le = float(math.sqrt(max(track.pos_cov_m2[2, 2], 1e-6)))
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    ev = ET.Element("event", {
        "version": "2.0", "uid": f"{sensor_uid}.{track.track_id}", "type": cot_type(track, hostile),
        "how": "m-p",                               # machine, passive sensor
        "time": fmt(now), "start": fmt(now), "stale": fmt(now + timedelta(seconds=stale_s)),
    })
    ET.SubElement(ev, "point", {"lat": f"{lat:.7f}", "lon": f"{lon:.7f}", "hae": f"{hae:.1f}", "ce": f"{ce:.1f}", "le": f"{le:.1f}"})
    detail = ET.SubElement(ev, "detail")
    ET.SubElement(detail, "track", {"speed": f"{track.speed_mps:.2f}", "course": f"{track.course_deg:.1f}"})
    ET.SubElement(detail, "contact", {"callsign": f"PNMB-{track.track_id}"})
    ET.SubElement(detail, "remarks").text = (
        f"{track.top_class} p={track.class_probs.get(track.top_class, 0):.2f} conf={track.confidence:.2f} "
        f"status={track.status} pairs={len(track.supporting_pairs)}")
    p = ET.SubElement(detail, "__penumbra", {"status": track.status, "confidence": f"{track.confidence:.3f}",
                                             "quality": f"{track.quality:.3f}", "n_pairs": str(len(track.supporting_pairs))})
    for c, v in track.class_probs.items():
        ET.SubElement(p, "class", {"name": c, "p": f"{v:.3f}"})
    for e in track.evidence:
        ET.SubElement(p, "evidence", {"kind": e.kind, "log_odds": f"{e.log_odds:+.2f}"}).text = e.statement
    return ET.tostring(ev, encoding="unicode")
