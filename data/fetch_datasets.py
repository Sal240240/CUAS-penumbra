"""Fetch public measured micro-Doppler / RF datasets for pretraining, per RT-11
(docs/10_red_team_ledger.md).

No dataset exists yet for ATSC-illuminated drone echoes at PENUMBRA's actual
bands — that is a WP6 field-collection deliverable, not something to fake by
scraping. What this script fetches is public data used to pretrain the
classifier head before real-world retraining (see penumbra/ml/train.py):

  1. KTH/SAAB 77 GHz drone/bird/human radar set — CC-BY-4.0, hosted on Zenodo,
     genuinely open (no login): this script downloads it automatically.
  2. DIAT-uSAT X-band micro-Doppler set — IEEE DataPort, gated behind either a
     paid subscription or an emailed educational-access request. This script
     cannot and does not attempt to download it; it prints the manual steps.
  3. DroneDetect RF (drone remote-control signal) set — also IEEE DataPort,
     gated behind a free account login. Same treatment.

Bypassing an account/paywall gate programmatically is not something this
script does, even for a "free" account — that is a manual, human step, and
pretending otherwise would be exactly the kind of shortcut this project's own
red-team process exists to catch.

Usage:
  python fetch_datasets.py list                 # show status of all sources
  python fetch_datasets.py fetch kth_saab_77ghz  # download the open one
  python fetch_datasets.py verify kth_saab_77ghz # checksum an existing download
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")


@dataclass(frozen=True)
class DatasetSource:
    key: str
    title: str
    citation: str
    license: str
    access: str  # 'open' | 'gated_account' | 'gated_educational_request'
    files: list  # list of {name, url, md5, size_bytes}
    manual_note: str = ""


SOURCES = {
    "kth_saab_77ghz": DatasetSource(
        key="kth_saab_77ghz",
        title="Radar measurements on drones, birds and humans with a 77 GHz FMCW sensor",
        citation="A. Karlsson, KTH Royal Institute of Technology, Zenodo, DOI:10.5281/zenodo.5845259, 2021. "
                 "Reference paper: A. Karlsson, M. Jansson, M. Hamalainen, 'Model-Aided Drone Classification "
                 "Using Convolutional Neural Networks,' IEEE Radar Conference, 2022.",
        license="CC BY 4.0",
        access="open",
        files=[
            {"name": "data_SAAB_SIRS_77GHz_FMCW.npy",
             "url": "https://zenodo.org/records/5845259/files/data_SAAB_SIRS_77GHz_FMCW.npy?download=1",
             "md5": "01d66ba7b1ccc04477a9e69b2813f251", "size_bytes": 1_600_000_000},
            {"name": "ReadMe.txt",
             "url": "https://zenodo.org/records/5845259/files/ReadMe.txt?download=1",
             "md5": "767d670bec773ee7c2360fa9ae2fddf4", "size_bytes": 2_900},
        ],
    ),
    "diat_usat": DatasetSource(
        key="diat_usat",
        title="DIAT-uSAT: micro-Doppler Signature Dataset of Small Unmanned Aerial Vehicle (SUAV)",
        citation="IEEE DataPort, https://ieee-dataport.org/documents/diat-msat-micro-doppler-signature-dataset-"
                 "small-unmanned-aerial-vehicle-suav — cite the two papers named on that page.",
        license="Not publicly stated; access-gated (see manual_note)",
        access="gated_educational_request",
        files=[],
        manual_note=(
            "Not auto-fetchable: requires either an IEEE DataPort subscription, or emailing the dataset "
            "contacts from an institutional address with subject 'DIAT-uSAT Dataset Educational Access "
            "Request' (see the dataset page). Once obtained, place the extracted archive at "
            "data/raw/diat_usat/ and re-run this script with 'verify diat_usat' to confirm the expected "
            "file count (4849 JPG micro-Doppler images per the dataset description)."
        ),
    ),
    "dronedetect": DatasetSource(
        key="dronedetect",
        title="DroneDetect Dataset: A Radio Frequency dataset of UAS Signals for Machine Learning "
              "Detection & Classification",
        citation="IEEE DataPort, https://ieee-dataport.org/open-access/dronedetect-dataset-radio-frequency-"
                 "dataset-unmanned-aerial-system-uas-signals-machine",
        license="Not publicly stated; free-account-gated",
        access="gated_account",
        files=[],
        manual_note=(
            "Not auto-fetchable: IEEE DataPort's 'Open Access' tier here still requires a free IEEE account "
            "login through their web UI (or their AWS S3 access path for logged-in users) — there is no "
            "anonymous HTTP endpoint to script against. Create a free account, download DroneDetect_V2.zip "
            "(65.76 GB), and place it at data/raw/dronedetect/ before re-running 'verify dronedetect'."
        ),
    ),
}


def _md5(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _download(url: str, dest: str) -> None:
    def _progress(count, block_size, total_size):
        if total_size <= 0:
            return
        pct = min(100.0, count * block_size * 100.0 / total_size)
        sys.stdout.write(f"\r  {os.path.basename(dest)}: {pct:5.1f}%")
        sys.stdout.flush()
    urllib.request.urlretrieve(url, dest, _progress)
    print()


def cmd_list() -> None:
    for src in SOURCES.values():
        print(f"[{src.access:^28s}] {src.key}")
        print(f"    {src.title}")
        print(f"    license: {src.license}")
        if src.manual_note:
            print(f"    {src.manual_note}")
        print()


def cmd_fetch(key: str) -> None:
    src = SOURCES.get(key)
    if src is None:
        print(f"unknown dataset '{key}'; run 'list' for options", file=sys.stderr)
        sys.exit(1)
    if src.access != "open":
        print(f"'{key}' is not open-access and cannot be auto-fetched.\n{src.manual_note}")
        sys.exit(1)
    out_dir = os.path.join(RAW_DIR, key)
    os.makedirs(out_dir, exist_ok=True)
    for f in src.files:
        dest = os.path.join(out_dir, f["name"])
        if os.path.exists(dest) and os.path.getsize(dest) == f["size_bytes"]:
            print(f"  {f['name']}: already present, skipping")
            continue
        print(f"  fetching {f['name']} ({f['size_bytes']/1e6:.0f} MB) from {f['url']}")
        _download(f["url"], dest)
    cmd_verify(key)


def cmd_verify(key: str) -> None:
    src = SOURCES.get(key)
    if src is None:
        print(f"unknown dataset '{key}'", file=sys.stderr)
        sys.exit(1)
    out_dir = os.path.join(RAW_DIR, key)
    if not src.files:
        n = len([f for f in os.listdir(out_dir)]) if os.path.isdir(out_dir) else 0
        print(f"{key}: {n} file(s) present in {out_dir} (no checksum manifest for gated sources)")
        return
    ok = True
    for f in src.files:
        path = os.path.join(out_dir, f["name"])
        if not os.path.exists(path):
            print(f"  MISSING: {f['name']}")
            ok = False
            continue
        digest = _md5(path)
        status = "OK" if digest == f["md5"] else "CHECKSUM MISMATCH"
        if digest != f["md5"]:
            ok = False
        print(f"  {f['name']}: {status}")
    print("verified" if ok else "one or more files failed verification")


def main(argv: Optional[list] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    fp = sub.add_parser("fetch")
    fp.add_argument("key", choices=list(SOURCES.keys()))
    vp = sub.add_parser("verify")
    vp.add_argument("key", choices=list(SOURCES.keys()))
    args = p.parse_args(argv)

    os.makedirs(RAW_DIR, exist_ok=True)
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "fetch":
        cmd_fetch(args.key)
    elif args.cmd == "verify":
        cmd_verify(args.key)


if __name__ == "__main__":
    main()
