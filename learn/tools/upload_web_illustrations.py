#!/usr/bin/env python3
"""Upload the generated bird illustrations to the progress bucket.

Reads the images written by ``build_web_illustrations.py`` and puts each one
at ``media/illustrations/<version>/<species_id>.webp``. The Worker serves the
same keys publicly through ``/media/...``; the bucket itself stays private.

Targets are the local wrangler emulation or the deployed bucket. Objects are
small and stable, so the tool uploads every file each run instead of trying to
guess remote state; reruns are idempotent.

Local wrangler writes share a single state database and fail under parallel
processes, so local uploads are sequential by default. Remote uploads are
parallel.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "build" / "media" / "illustrations" / "v1"
WRANGLER_CWD = ROOT / "learn" / "cloudflare"
CACHE_CONTROL = "public, max-age=31536000, immutable"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--local", action="store_const", const="local", dest="target")
    target.add_argument("--remote", action="store_const", const="remote", dest="target")
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"generated image directory (default {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--bucket",
        default="birds-progress",
        help="R2 bucket (default birds-progress)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="parallel uploads (default: 1 local, 6 remote)",
    )
    return parser.parse_args(argv)


def upload(key: str, path: Path, bucket: str, target: str) -> None:
    command = [
        "npx",
        "wrangler",
        "r2",
        "object",
        "put",
        f"{bucket}/{key}",
        "--file",
        str(path),
        "--content-type",
        "image/webp",
        "--cache-control",
        CACHE_CONTROL,
        "--" + target,
    ]
    result = subprocess.run(
        command,
        cwd=WRANGLER_CWD,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f"upload failed: {key}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    directory = args.dir
    if not directory.is_dir():
        raise SystemExit(
            f"upload_web_illustrations: {directory} is missing; run "
            "learn-web-illustrations first"
        )
    files = sorted(directory.glob("*.webp"))
    if not files:
        raise SystemExit(f"upload_web_illustrations: no images in {directory}")

    jobs = args.jobs
    if jobs is None:
        jobs = 1 if args.target == "local" else 6
    jobs = max(1, jobs)
    version = directory.name
    total = len(files)
    done = 0
    errors: list[str] = []
    lock = threading.Lock()

    def put(path: Path) -> None:
        key = f"media/illustrations/{version}/{path.name}"
        upload(key, path, args.bucket, args.target)

    print(
        f"upload_web_illustrations: {total} images to {args.target} "
        f"bucket {args.bucket} ({jobs} job{'s' if jobs != 1 else ''})"
    )
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(put, path): path for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                future.result()
                with lock:
                    done += 1
                    if done % 25 == 0 or done == total:
                        print(f"upload_web_illustrations: {done}/{total}", flush=True)
            except Exception as exc:  # noqa: BLE001 - report per image
                with lock:
                    errors.append(f"{path.name}: {exc}")

    if errors:
        for error in errors[:10]:
            print(error, file=sys.stderr)
        raise SystemExit(
            f"upload_web_illustrations: {len(errors)} uploads failed"
        )
    print(f"upload_web_illustrations: uploaded {done} images ({args.target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
