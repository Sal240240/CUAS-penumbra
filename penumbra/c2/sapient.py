"""SAPIENT adapter (BSI Flex 335 v2.0 / SAPIENT v7 message structure).

SAPIENT (Sensing for Asset Protection using Integrated Electronic Networked
Technology) is the UK Dstl-originated open ICD adopted by NATO C-UAS trials and
listed by DND as a protocol of interest. v7 is Protobuf-based; the JSON emitted
here mirrors the DetectionReport / StatusReport / Registration message fields
(names and units follow the published specification) so that a protobuf
serialiser can be dropped in without changing the mapping. Location uses the
GEODETIC_WGS84 datum with 1-sigma errors, as SAPIENT requires.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import uuid
import numpy as np
from ..tracking.schema import Track
from .geodesy import enu_to_geodetic

NODE_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "penumbra.fabric"))


def _ts(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")


def registration(node_name: str = "PENUMBRA Fabric") -> dict:
    return {
        "node_id": NODE_ID, "timestamp": _ts(),
        "registration": {
            "node_definition": [{"node_type": "RADAR", "node_sub_type": ["Passive multistatic RF"]}],
            "icd_version": "BSI Flex 335 v2.0",
            "name": node_name, "short_name": "PNMB",
            "capabilities": [{"category": "detection", "type": "passive_bistatic_radar", "units": "m", "value": "micro/mini UAS"}],
            "status_definition": {"status_interval": {"units": "seconds", "value": 5}},
            "mode_definition": [{"mode_name": "surveillance", "mode_type": "Permanent",
                                 "detection_definition": [{"location_type": {"location_units": "DECIMAL_DEGREES", "location_datum": "WGS84_E"}}],
                                 "task": {"region_definition": {"region_type": ["AREA"]}}}],
            "dependent_nodes": [],
        },
    }


def status_report(nodes_healthy: int, nodes_total: int, gnss_locked: bool, now: datetime | None = None) -> dict:
    return {
        "node_id": NODE_ID, "timestamp": _ts(now),
        "status_report": {
            "report_id": str(uuid.uuid4()),
            "system": "OK" if nodes_healthy == nodes_total else ("WARNING" if nodes_healthy >= 3 else "ERROR"),
            "info": "New",
            "status": [
                {"status_type": "mesh_nodes", "status_value": f"{nodes_healthy}/{nodes_total}"},
                {"status_type": "timing", "status_value": "GNSS-disciplined" if gnss_locked else "holdover (PTP)"},
            ],
        },
    }


def detection_report(track: Track, ref=None, now: datetime | None = None) -> dict:
    lat, lon, hae = enu_to_geodetic(track.pos_enu_m, ref) if ref else enu_to_geodetic(track.pos_enu_m)
    sx, sy, sz = (math.sqrt(max(track.pos_cov_m2[i, i], 1e-6)) for i in range(3))
    top = track.top_class
    return {
        "node_id": NODE_ID, "timestamp": _ts(now),
        "detection_report": {
            "report_id": str(uuid.uuid4()),
            "object_id": track.track_id,
            "task_id": "surveillance",
            "state": {"tentative": "TENTATIVE", "confirmed": "CONFIRMED", "coasting": "COASTING", "lost": "LOST"}.get(track.status, "UNKNOWN"),
            "location": {"x": lon, "y": lat, "z": hae, "x_error": sx, "y_error": sy, "z_error": sz,
                         "coordinate_system": "LAT_LNG_DEG_M", "datum": "WGS84_E"},
            "detection_confidence": round(float(track.confidence), 3),
            "track_info": [
                {"type": "speed", "value": round(track.speed_mps, 2), "units": "m/s"},
                {"type": "course", "value": round(track.course_deg, 1), "units": "degrees"},
                {"type": "age", "value": round(track.age_s, 1), "units": "seconds"},
            ],
            "object_info": [{"type": "supporting_pairs", "value": str(len(track.supporting_pairs))}],
            "classification": [
                {"type": {"drone": "Air Vehicle.UAV.Multirotor", "bird": "Animal.Bird", "vehicle": "Ground Vehicle",
                          "clutter": "Clutter", "unknown": "Unknown"}[c], "confidence": round(float(p), 3)}
                for c, p in sorted(track.class_probs.items(), key=lambda kv: -kv[1]) if p > 0.01
            ],
            "behaviour": [{"type": "hover" if track.speed_mps < 1.0 else "transit", "confidence": 0.7}],
            "penumbra_evidence": [{"kind": e.kind, "log_odds": round(e.log_odds, 2), "statement": e.statement} for e in track.evidence],
        },
    }
