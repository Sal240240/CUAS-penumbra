"""Train and evaluate PenumbraNet on simulator data.

    python -m penumbra.ml.train --episodes 120 --epochs 12 --out ml_runs/demo

Outputs: checkpoint (model + ops + config), metrics.json (detection P/R at the
conformal threshold, class accuracy, calibration), and a few example arrays for
the documentation figures.
"""
from __future__ import annotations
import argparse, json, os, time
from typing import Dict, List
import numpy as np
import torch
from .dataset import build_dataset, backprojection_operator, CLASS_NAMES, default_pairs
from .model import PenumbraNet, BANDS, focal_bce, evidential_nll
from .calibration import conformal_threshold, peaks_from_heatmap, match_peaks


def make_windows(data: Dict, n_frames: int):
    """Sliding windows of n_frames within each episode; label = last frame."""
    rd, ep = data["rd"], data["episode"]
    idx = []
    for i in range(n_frames - 1, len(rd)):
        if ep[i] == ep[i - n_frames + 1]:
            idx.append(i)
    return np.asarray(idx)


def build_model(pairs, bev_size, n_doppler, extent, n_frames, base=32):
    ops = np.stack([backprojection_operator(p, extent, bev_size) for p in pairs])
    band_index = [BANDS.index(p.kind) for p in pairs]
    return PenumbraNet(ops, band_index, bev_size, n_doppler, n_frames=n_frames, base=base), ops, band_index


def evaluate(model, data, idx, n_frames, thr, device, extent, bev_size, batch=8):
    model.eval()
    tp = fp = fn = 0
    cls_correct = cls_total = 0
    pos_err = []
    with torch.no_grad():
        for s in range(0, len(idx), batch):
            ii = idx[s:s + batch]
            x = torch.as_tensor(np.stack([data["rd"][i - n_frames + 1:i + 1] for i in ii])).to(device)
            out = model(x)
            heat = torch.sigmoid(out["occ"]).cpu().numpy()
            cls = out["cls"].argmax(1).cpu().numpy()
            for j, i in enumerate(ii):
                pk = peaks_from_heatmap(heat[j], thr)
                truth = [t for t in data["targets"][i] if t["label"] in ("drone", "bird")]
                m = match_peaks(pk, truth, extent, bev_size, max_cells=2.0)
                tp += m["tp"]; fp += m["fp"]; fn += m["fn"]; pos_err += m["err_m"]
                for (r, c, _), t in m["pairs"]:
                    cls_total += 1
                    cls_correct += int(CLASS_NAMES[cls[j, r, c]] == t["label"])
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    return {"precision": prec, "recall": rec, "f1": 2 * prec * rec / max(prec + rec, 1e-9),
            "tp": tp, "fp": fp, "fn": fn, "fa_per_frame": fp / max(len(idx), 1),
            "class_acc": cls_correct / max(cls_total, 1),
            "pos_rmse_m": float(np.sqrt(np.mean(np.square(pos_err)))) if pos_err else None,
            "n_frames": int(len(idx))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=80)
    ap.add_argument("--val-episodes", type=int, default=20)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--base", type=int, default=32)
    ap.add_argument("--fa-per-frame", type=float, default=0.05, help="conformal false-alarm budget")
    ap.add_argument("--out", default="ml_runs/demo")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    t0 = time.time()
    train, pairs, scene = build_dataset(args.episodes, seed=args.seed)
    val, _, _ = build_dataset(args.val_episodes, seed=args.seed + 10_000, scene=scene)
    print(f"data: train {train['rd'].shape} val {val['rd'].shape} pairs {len(pairs)} ({time.time()-t0:.0f}s)")
    bev, ext, n_dop = train["bev_size"], train["extent_m"], train["rd"].shape[-1]
    model, ops, band_index = build_model(pairs, bev, n_dop, ext, args.frames, args.base)
    model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model params: {n_params/1e6:.2f} M")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * max(1, len(make_windows(train, args.frames)) // args.batch))
    tr_idx = make_windows(train, args.frames)
    va_idx = make_windows(val, args.frames)
    history = []
    for ep in range(args.epochs):
        model.train()
        perm = np.random.default_rng(ep).permutation(tr_idx)
        losses = []
        for s in range(0, len(perm) - args.batch + 1, args.batch):
            ii = perm[s:s + args.batch]
            x = torch.as_tensor(np.stack([train["rd"][i - args.frames + 1:i + 1] for i in ii])).to(device)
            y_occ = torch.as_tensor(np.stack([train["bev_occ"][i] for i in ii])).to(device)
            y_cls = torch.as_tensor(np.stack([train["bev_cls"][i] for i in ii])).to(device)
            out = model(x)
            l_occ = focal_bce(out["occ"], y_occ)
            w = torch.ones(4, device=device); w[0] = 0.05           # background dominates
            l_cls = torch.nn.functional.cross_entropy(out["cls"], y_cls, weight=w)
            l_unc = evidential_nll(out["occ"].detach(), out["unc"], y_occ)
            loss = l_occ + l_cls + 0.1 * l_unc
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step(); sched.step()
            losses.append([loss.item(), l_occ.item(), l_cls.item(), l_unc.item()])
        m = np.mean(losses, axis=0)
        history.append({"epoch": ep, "loss": float(m[0]), "occ": float(m[1]), "cls": float(m[2]), "unc": float(m[3])})
        print(f"epoch {ep:02d} loss {m[0]:.3f} (occ {m[1]:.3f} cls {m[2]:.3f} unc {m[3]:.3f})  {time.time()-t0:.0f}s")

    # conformal threshold on the validation set for the false-alarm budget, then metrics
    thr = conformal_threshold(model, val, va_idx, args.frames, device, ext, bev, args.fa_per_frame)
    metrics = evaluate(model, val, va_idx, args.frames, thr, device, ext, bev)
    metrics.update({"threshold": float(thr), "params": int(n_params), "history": history,
                    "train_frames": int(len(tr_idx)), "pairs": len(pairs), "fa_budget_per_frame": args.fa_per_frame})
    print(json.dumps({k: v for k, v in metrics.items() if k != "history"}, indent=2))
    torch.save({"state": model.state_dict(), "ops": ops, "band_index": band_index, "bev": bev, "extent": ext,
                "n_doppler": n_dop, "frames": args.frames, "base": args.base, "threshold": float(thr),
                "pairs": [p.__dict__ for p in pairs]}, os.path.join(args.out, "penumbra_net.pt"))
    with open(os.path.join(args.out, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    # example for docs/webapp
    i = va_idx[len(va_idx) // 2]
    with torch.no_grad():
        x = torch.as_tensor(val["rd"][i - args.frames + 1:i + 1][None]).to(device)
        out = model(x)
    np.savez_compressed(os.path.join(args.out, "example.npz"), rd=val["rd"][i], heat=torch.sigmoid(out["occ"])[0].cpu().numpy(),
                        cls=out["cls"][0].argmax(0).cpu().numpy(), occ_true=val["bev_occ"][i], unc=out["unc"][0].cpu().numpy(),
                        targets=json.dumps(val["targets"][i]))
    return metrics


if __name__ == "__main__":
    main()
