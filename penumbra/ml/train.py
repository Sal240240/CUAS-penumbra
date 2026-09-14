"""Train and evaluate PenumbraNet on simulator data.

    python -m penumbra.ml.train --episodes 120 --epochs 12 --out ml_runs/demo
    python -m penumbra.ml.train --resume ml_runs/v1/penumbra_net.pt --epochs 8 --out ml_runs/v2

Outputs: checkpoint (model + ops + config), metrics.json (detection P/R at the
conformal threshold, class accuracy, calibration), and a few example arrays for
the documentation figures.

Validation runs every `--val-every` epochs and the best checkpoint by F1 is kept
separately from the last one, so a run that overfits late does not silently
overwrite its own best weights. `--resume` continues training from an existing
checkpoint, which requires the same scene geometry (the backprojection operators
are baked into the model) — the shapes are checked, not assumed.
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


def batch_tensor(data, ii, n_frames, device):
    """Stack a window batch and cast to float32 (the store may be float16)."""
    x = np.stack([data["rd"][i - n_frames + 1:i + 1] for i in ii])
    return torch.as_tensor(x).float().to(device)


def evaluate(model, data, idx, n_frames, thr, device, extent, bev_size, batch=8):
    model.eval()
    tp = fp = fn = 0
    cls_correct = cls_total = 0
    pos_err = []
    with torch.no_grad():
        for s in range(0, len(idx), batch):
            ii = idx[s:s + batch]
            x = batch_tensor(data, ii, n_frames, device)
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
    ap.add_argument("--resume", default=None, help="checkpoint to continue training from (same scene geometry)")
    ap.add_argument("--val-every", type=int, default=2, help="run validation every N epochs (0 = only at the end)")
    ap.add_argument("--fp16-store", action="store_true",
                    help="hold the range-Doppler dataset as float16 (halves RAM; batches are cast to float32)")
    ap.add_argument("--progress-every", type=int, default=10,
                    help="print an intra-epoch progress line every N steps (0 to disable); "
                         "CPU epochs are long enough that a silent loop is indistinguishable from a hung one")
    ap.add_argument("--threads", type=int, default=0, help="torch intra-op threads (0 = leave default)")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    torch.manual_seed(args.seed)
    if args.threads:
        torch.set_num_threads(args.threads)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    t0 = time.time()
    train, pairs, scene = build_dataset(args.episodes, seed=args.seed)
    val, _, _ = build_dataset(args.val_episodes, seed=args.seed + 10_000, scene=scene)
    if args.fp16_store:
        train["rd"] = train["rd"].astype(np.float16)
        val["rd"] = val["rd"].astype(np.float16)
    print(f"data: train {train['rd'].shape} ({train['rd'].nbytes/1e6:.0f} MB) "
          f"val {val['rd'].shape} pairs {len(pairs)} ({time.time()-t0:.0f}s)", flush=True)
    bev, ext, n_dop = train["bev_size"], train["extent_m"], train["rd"].shape[-1]
    model, ops, band_index = build_model(pairs, bev, n_dop, ext, args.frames, args.base)
    if args.resume:
        ck = torch.load(args.resume, map_location="cpu", weights_only=False)
        if ck["ops"].shape != ops.shape or ck["frames"] != args.frames or ck["base"] != args.base:
            raise SystemExit(
                f"--resume checkpoint is incompatible: ops {ck['ops'].shape} vs {ops.shape}, "
                f"frames {ck['frames']} vs {args.frames}, base {ck['base']} vs {args.base}. "
                "Resuming requires the same scene geometry and model shape.")
        model.load_state_dict(ck["state"])
        print(f"resumed weights from {args.resume}", flush=True)
    model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model params: {n_params/1e6:.2f} M")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * max(1, len(make_windows(train, args.frames)) // args.batch))
    tr_idx = make_windows(train, args.frames)
    va_idx = make_windows(val, args.frames)
    history = []
    best = {"f1": -1.0, "epoch": -1}
    best_path = os.path.join(args.out, "penumbra_net_best.pt")

    def checkpoint(path, threshold):
        torch.save({"state": model.state_dict(), "ops": ops, "band_index": band_index, "bev": bev, "extent": ext,
                    "n_doppler": n_dop, "frames": args.frames, "base": args.base, "threshold": float(threshold),
                    "pairs": [p.__dict__ for p in pairs]}, path)

    n_steps = len(range(0, len(tr_idx) - args.batch + 1, args.batch))
    print(f"steps/epoch: {n_steps} (batch {args.batch}, {len(tr_idx)} windows)", flush=True)
    for ep in range(args.epochs):
        model.train()
        perm = np.random.default_rng(ep).permutation(tr_idx)
        losses = []
        ep_t0 = time.time()
        for step, s in enumerate(range(0, len(perm) - args.batch + 1, args.batch)):
            ii = perm[s:s + args.batch]
            if args.progress_every and step and step % args.progress_every == 0:
                rate = (time.time() - ep_t0) / step
                print(f"  ep {ep:02d} step {step}/{n_steps}  {rate:.2f}s/step  "
                      f"eta_epoch {(n_steps - step) * rate / 60:.1f} min", flush=True)
            x = batch_tensor(train, ii, args.frames, device)
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
        row = {"epoch": ep, "loss": float(m[0]), "occ": float(m[1]), "cls": float(m[2]), "unc": float(m[3])}
        msg = f"epoch {ep:02d} loss {m[0]:.3f} (occ {m[1]:.3f} cls {m[2]:.3f} unc {m[3]:.3f})"

        due = args.val_every > 0 and ((ep + 1) % args.val_every == 0 or ep == args.epochs - 1)
        if due:
            thr_ep = conformal_threshold(model, val, va_idx, args.frames, device, ext, bev, args.fa_per_frame)
            vm = evaluate(model, val, va_idx, args.frames, thr_ep, device, ext, bev)
            row.update({"val_f1": vm["f1"], "val_precision": vm["precision"], "val_recall": vm["recall"],
                        "val_threshold": float(thr_ep), "val_class_acc": vm["class_acc"]})
            msg += f" | val F1 {vm['f1']:.3f} P {vm['precision']:.3f} R {vm['recall']:.3f}"
            if vm["f1"] > best["f1"]:
                best = {"f1": vm["f1"], "epoch": ep, "threshold": float(thr_ep)}
                checkpoint(best_path, thr_ep)
                msg += "  <- best"
        history.append(row)
        print(f"{msg}  {time.time()-t0:.0f}s", flush=True)

    # Final metrics are reported from the best checkpoint, not whatever the last
    # epoch happened to land on.
    if best["epoch"] >= 0:
        model.load_state_dict(torch.load(best_path, map_location=device, weights_only=False)["state"])
        print(f"evaluating best checkpoint (epoch {best['epoch']}, val F1 {best['f1']:.3f})", flush=True)
    thr = conformal_threshold(model, val, va_idx, args.frames, device, ext, bev, args.fa_per_frame)
    metrics = evaluate(model, val, va_idx, args.frames, thr, device, ext, bev)
    metrics["best_epoch"] = best["epoch"]
    metrics.update({"threshold": float(thr), "params": int(n_params), "history": history,
                    "train_frames": int(len(tr_idx)), "pairs": len(pairs), "fa_budget_per_frame": args.fa_per_frame})
    print(json.dumps({k: v for k, v in metrics.items() if k != "history"}, indent=2))
    checkpoint(os.path.join(args.out, "penumbra_net.pt"), thr)
    with open(os.path.join(args.out, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    # example for docs/webapp
    i = va_idx[len(va_idx) // 2]
    with torch.no_grad():
        x = torch.as_tensor(val["rd"][i - args.frames + 1:i + 1][None]).float().to(device)
        out = model(x)
    np.savez_compressed(os.path.join(args.out, "example.npz"), rd=val["rd"][i], heat=torch.sigmoid(out["occ"])[0].cpu().numpy(),
                        cls=out["cls"][0].argmax(0).cpu().numpy(), occ_true=val["bev_occ"][i], unc=out["unc"][0].cpu().numpy(),
                        targets=json.dumps(val["targets"][i]))
    return metrics


if __name__ == "__main__":
    main()
