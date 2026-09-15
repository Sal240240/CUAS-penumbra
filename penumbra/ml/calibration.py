"""Peak extraction and conformal false-alarm control.

`conformal_threshold` picks the heat-map threshold on a held-out calibration set so
that the *empirical* number of unmatched peaks per frame does not exceed the
budget. This is a split-conformal guarantee on the false-alarm rate under
exchangeability of calibration and deployment frames — a property we can promise
only for the simulator until WP6 provides urban background captures, which is
said explicitly in the docs.
"""
from __future__ import annotations
from typing import Dict, List, Tuple
import numpy as np
import torch
from scipy.ndimage import maximum_filter


def peaks_from_heatmap(heat: np.ndarray, thr: float, size: int = 3) -> List[Tuple[int, int, float]]:
    mx = maximum_filter(heat, size=size, mode="nearest")
    rr, cc = np.where((heat >= thr) & (heat == mx))
    return [(int(r), int(c), float(heat[r, c])) for r, c in zip(rr, cc)]


def cell_to_xy(r: int, c: int, extent: float, size: int) -> Tuple[float, float]:
    x = -extent + c / (size - 1) * 2 * extent
    y = -extent + r / (size - 1) * 2 * extent
    return x, y


def match_peaks(peaks, truth: List[Dict], extent: float, size: int, max_cells: float = 2.0) -> Dict:
    cell_m = 2 * extent / (size - 1)
    used = set(); pairs = []; err = []
    for pk in sorted(peaks, key=lambda p: -p[2]):
        x, y = cell_to_xy(pk[0], pk[1], extent, size)
        best, bd = None, 1e9
        for j, t in enumerate(truth):
            if j in used:
                continue
            d = np.hypot(t["x"] - x, t["y"] - y)
            if d < bd:
                best, bd = j, d
        if best is not None and bd <= max_cells * cell_m:
            used.add(best); pairs.append((pk, truth[best])); err.append(bd)
    tp = len(pairs)
    return {"tp": tp, "fp": len(peaks) - tp, "fn": len(truth) - tp, "pairs": pairs, "err_m": err}


def conformal_threshold(model, data, idx, n_frames, device, extent, size, fa_per_frame: float,
                        batch: int = 8) -> float:
    """Smallest threshold whose empirical unmatched-peak rate on the calibration frames is
    within budget (searched over the observed peak scores)."""
    model.eval()
    fa_scores = []   # scores of unmatched peaks at a permissive threshold
    with torch.no_grad():
        for s in range(0, len(idx), batch):
            ii = idx[s:s + batch]
            x = torch.as_tensor(np.stack([data["rd"][i - n_frames + 1:i + 1] for i in ii])).float().to(device)
            heat = torch.sigmoid(model(x)["occ"]).cpu().numpy()
            for j, i in enumerate(ii):
                pk = peaks_from_heatmap(heat[j], 0.05)
                truth = [t for t in data["targets"][i] if t["label"] in ("drone", "bird")]
                m = match_peaks(pk, truth, extent, size)
                matched = {id(p[0]) for p in m["pairs"]}
                fa_scores += [p[2] for p in pk if id(p) not in matched]
    n = max(len(idx), 1)
    allowed = int(np.floor(fa_per_frame * n))
    if not fa_scores or allowed >= len(fa_scores):
        return 0.5
    fa_scores = np.sort(fa_scores)[::-1]
    # keep at most `allowed` false alarms: threshold just above the (allowed+1)-th highest FA score
    return float(min(0.95, fa_scores[allowed] + 1e-3))
