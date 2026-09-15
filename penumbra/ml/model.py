"""PENUMBRA fusion network: learned multistatic backprojection.

Inputs per frame: N_pairs range-Doppler surfaces (dB above floor) plus the fixed
scene geometry. Processing:

1. Per-pair Doppler encoder. A small 1-D CNN over the Doppler axis of every delay
   bin produces (a) a "motion energy" scalar that ignores the clutter notch, and
   (b) a K-dim micro-Doppler descriptor (line spacing / spread), for each delay bin.
2. Physical backprojection. Each pair's per-delay features are spread along that
   pair's bistatic-range ellipses into the BEV grid with the *true* geometry
   operator (dataset.backprojection_operator). No learning here: this is the
   multistatic radar equation made differentiable.
3. Band-wise fusion. Backprojected maps are grouped by band (ATSC / LTE / NR) and
   summed, so the network sees three physically distinct evidence layers plus a
   count-of-pairs layer for coverage awareness.
4. Spatio-temporal U-Net over (frames x channels x H x W) resolves ellipse
   intersections into targets, suppresses ghosts and vehicles (no altitude but
   street-constrained kinematics and no rotor lines), and outputs
     occ  (H, W) logits  — airborne target heat-map
     cls  (4, H, W)      — none / drone / bird / vehicle
     unc  (H, W)         — evidential log-variance for calibrated confidence.

The design is deliberately shallow (~0.4 M parameters) so it runs on a Jetson
Orin Nano at mesh frame rate, and every intermediate map is physically interpretable
for the reasoning layer.
"""
from __future__ import annotations
from typing import Dict, List
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

BANDS = ["atsc", "lte", "nr"]


class DopplerEncoder(nn.Module):
    """1-D CNN across Doppler for every delay bin. Input (B, P, D, F) -> (B, P, D, K+1)."""
    def __init__(self, n_doppler: int, k_desc: int = 8):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 16, 7, padding=3), nn.GELU(),
            nn.Conv1d(16, 32, 7, padding=3, stride=2), nn.GELU(),
            nn.Conv1d(32, 32, 5, padding=2, stride=2), nn.GELU(),
            nn.AdaptiveAvgPool1d(4), nn.Flatten(),
            nn.Linear(128, 64), nn.GELU(), nn.Linear(64, k_desc + 1),
        )

    def forward(self, rd: torch.Tensor) -> torch.Tensor:
        b, p, d, f = rd.shape
        x = rd.reshape(b * p * d, 1, f) / 30.0          # dB scale -> O(1)
        y = self.net(x)
        return y.reshape(b, p, d, -1)


class Backproject(nn.Module):
    """Fixed physical operator: (B, P, D, C) per-delay features -> (B, bands*C+1, H, W)."""
    def __init__(self, ops: np.ndarray, band_index: List[int], bev_size: int):
        super().__init__()
        self.register_buffer("ops", torch.as_tensor(ops))            # (P, D, HW)
        self.register_buffer("band", torch.as_tensor(band_index))    # (P,)
        self.bev = bev_size
        self.n_bands = len(BANDS)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        b, p, d, c = feats.shape
        # (B, P, C, HW)
        proj = torch.einsum("bpdc,pdh->bpch", feats, self.ops)
        out = []
        for k in range(self.n_bands):
            m = (self.band == k)
            if m.any():
                out.append(proj[:, m].sum(dim=1))
            else:
                out.append(torch.zeros(b, c, self.bev * self.bev, device=feats.device))
        # coverage channel: how many pairs touch each cell at all
        cov = self.ops.sum(dim=1).gt(0).float().sum(dim=0)   # (HW,)
        cov = cov.expand(b, 1, -1) / max(p, 1)
        x = torch.cat(out + [cov], dim=1)
        return x.reshape(b, -1, self.bev, self.bev)


class ConvBlock(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.net = nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1), nn.GroupNorm(8, cout), nn.GELU(),
                                 nn.Conv2d(cout, cout, 3, padding=1), nn.GroupNorm(8, cout), nn.GELU())

    def forward(self, x):
        return self.net(x)


class SpatioTemporalUNet(nn.Module):
    """Frames are stacked on channels (early fusion) — cheap and sufficient for 3-6 frame windows."""
    def __init__(self, cin: int, n_frames: int, base: int = 32, n_cls: int = 4):
        super().__init__()
        c = cin * n_frames
        self.e1 = ConvBlock(c, base)
        self.e2 = ConvBlock(base, base * 2)
        self.e3 = ConvBlock(base * 2, base * 4)
        self.d2 = ConvBlock(base * 4 + base * 2, base * 2)
        self.d1 = ConvBlock(base * 2 + base, base)
        self.occ = nn.Conv2d(base, 1, 1)
        self.cls = nn.Conv2d(base, n_cls, 1)
        self.unc = nn.Conv2d(base, 1, 1)
        nn.init.constant_(self.occ.bias, -4.0)      # start with p(target) ~ 0.02 everywhere (CenterNet init)

    def forward(self, x):
        e1 = self.e1(x)
        e2 = self.e2(F.max_pool2d(e1, 2))
        e3 = self.e3(F.max_pool2d(e2, 2))
        d2 = self.d2(torch.cat([F.interpolate(e3, scale_factor=2, mode="bilinear", align_corners=False), e2], 1))
        d1 = self.d1(torch.cat([F.interpolate(d2, scale_factor=2, mode="bilinear", align_corners=False), e1], 1))
        return {"occ": self.occ(d1)[:, 0], "cls": self.cls(d1), "unc": self.unc(d1)[:, 0]}


class PenumbraNet(nn.Module):
    def __init__(self, ops: np.ndarray, band_index: List[int], bev_size: int, n_doppler: int,
                 n_frames: int = 3, k_desc: int = 8, base: int = 32):
        super().__init__()
        self.n_frames = n_frames
        self.enc = DopplerEncoder(n_doppler, k_desc)
        self.bp = Backproject(ops, band_index, bev_size)
        cin = len(BANDS) * (k_desc + 1) + 1
        self.unet = SpatioTemporalUNet(cin, n_frames, base)

    def forward(self, rd_frames: torch.Tensor) -> Dict[str, torch.Tensor]:
        """rd_frames: (B, T, P, D, F) with T == n_frames (oldest first)."""
        b, t, p, d, f = rd_frames.shape
        feats = self.enc(rd_frames.reshape(b * t, p, d, f))
        feats = F.softplus(feats)                       # energies are non-negative
        bev = self.bp(feats)                            # (B*T, C, H, W)
        bev = bev.reshape(b, t * bev.shape[1], bev.shape[2], bev.shape[3])
        return self.unet(bev)


def focal_bce(logits: torch.Tensor, target: torch.Tensor, alpha: float = 2.0, beta: float = 4.0) -> torch.Tensor:
    """CenterNet-style penalty-reduced focal loss on a Gaussian heat-map target."""
    p = torch.sigmoid(logits).clamp(1e-4, 1 - 1e-4)
    pos = target.ge(0.99).float()
    neg_w = (1 - target).pow(beta)
    pos_loss = -(1 - p).pow(alpha) * torch.log(p) * pos
    neg_loss = -p.pow(alpha) * torch.log(1 - p) * neg_w * (1 - pos)
    n_pos = pos.sum().clamp(min=1.0)
    return (pos_loss.sum() + neg_loss.sum()) / n_pos


def evidential_nll(logits: torch.Tensor, log_var: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Heteroscedastic Gaussian NLL on the heat-map: teaches `unc` to grow where the
    evidence is ambiguous (ghost intersections, single-pair coverage)."""
    err = (torch.sigmoid(logits) - target) ** 2
    return (0.5 * torch.exp(-log_var) * err + 0.5 * log_var).mean()
