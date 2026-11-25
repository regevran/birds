#!/usr/bin/env python3
"""Fetch and resize the browser client's bird illustrations.

``learn/web/illustrations.json`` pins one source sticker per dataset species
(CC BY 4.0, see its ``source`` block). This tool downloads those stickers from
the pinned jsDelivr commit, resizes them to the configured longest side and
writes WebP copies under the disposable build tree, ready for the media upload
targets. The images are not committed and are not part of the static client
tree; the Worker serves them from R2.

Runs are incremental: when the build manifest matches the configuration and
every output exists, nothing is downloaded again. ``--force`` rebuilds all.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on the local toolchain
    raise SystemExit(
        "build_web_illustrations: Pillow is required "
        "(python3 -m pip install --user Pillow)"
    )

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "learn" / "web" / "illustrations.json"
DEFAULT_DATA = ROOT / "data" / "out" / "israel_birds_final.json"
DEFAULT_OUT = ROOT / "build" / "media" / "illustrations"
DEFAULT_CACHE = ROOT / "build" / "media-cache"
CDN = "https://cdn.jsdelivr.net/gh/alchaincyf/huashu-bird-sticker@{commit}/"
USER_AGENT = "birds-trainer-build"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"species-to-sticker manifest (default {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
        help=f"dataset used to check coverage (default {DEFAULT_DATA})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"build output root (default {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help=f"downloaded sticker cache (default {DEFAULT_CACHE})",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=8,
        help="parallel downloads (default 8)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild every image even when the outputs are current",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"build_web_illustrations: cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"build_web_illustrations: invalid JSON in {path}: {exc}")


def species_ids(path: Path) -> list[str]:
    birds = load_json(path)
    if not isinstance(birds, list):
        raise SystemExit(f"build_web_illustrations: {path} is not a list")
    ids: list[str] = []
    for bird in birds:
        try:
            ids.append(f"{bird['genus'].lower()}-{bird['epithet'].lower()}")
        except (KeyError, AttributeError):
            raise SystemExit(
                f"build_web_illustrations: {path} has a bird without genus/epithet"
            )
    return ids


def load_manifest(path: Path) -> dict:
    document = load_json(path)
    if not isinstance(document, dict):
        raise SystemExit(f"build_web_illustrations: {path} is not an object")
    source = document.get("source")
    stickers = document.get("stickers")
    for field in ("asset_version", "size", "quality"):
        if field not in document:
            raise SystemExit(f"build_web_illustrations: {path} lacks {field!r}")
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("commit"), str)
        or not source["commit"]
    ):
        raise SystemExit(f"build_web_illustrations: {path} lacks source.commit")
    if not isinstance(stickers, dict) or not stickers:
        raise SystemExit(f"build_web_illustrations: {path} lacks stickers")
    for species_id, sticker in stickers.items():
        if not isinstance(sticker, str) or not sticker.endswith(".webp"):
            raise SystemExit(
                f"build_web_illustrations: bad sticker path for {species_id!r}"
            )
    return document


def check_coverage(manifest: dict, ids: list[str]) -> None:
    wanted = set(ids)
    mapped = set(manifest["stickers"])
    if wanted != mapped:
        missing = sorted(wanted - mapped)
        extra = sorted(mapped - wanted)
        detail = []
        if missing:
            detail.append(f"missing {len(missing)}: {', '.join(missing[:5])}")
        if extra:
            detail.append(f"extra {len(extra)}: {', '.join(extra[:5])}")
        raise SystemExit(
            "build_web_illustrations: manifest does not match the dataset ("
            + "; ".join(detail)
            + ")"
        )


def output_path(out: Path, asset_version: str, species_id: str) -> Path:
    return out / asset_version / f"{species_id}.webp"


def build_manifest_path(out: Path, asset_version: str) -> Path:
    return out / asset_version / "manifest.json"


def current_build(out: Path, asset_version: str, config: dict) -> dict | None:
    path = build_manifest_path(out, asset_version)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expected = {
        "asset_version": config["asset_version"],
        "source_commit": config["source"]["commit"],
        "size": config["size"],
        "quality": config["quality"],
    }
    for key, value in expected.items():
        if document.get(key) != value:
            return None
    files = document.get("files")
    if not isinstance(files, dict):
        return None
    for species_id, size in files.items():
        path = output_path(out, asset_version, species_id)
        if not path.is_file() or path.stat().st_size != size:
            return None
    return document


def fetch(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if not data.startswith(b"RIFF") or b"WEBP" not in data[:16]:
                raise ValueError("response is not a WebP image")
            temporary = destination.with_suffix(destination.suffix + ".part")
            temporary.write_bytes(data)
            temporary.replace(destination)
            return
        except (OSError, ValueError) as exc:
            last_error = exc
            time.sleep(1 + attempt * 2)
    raise RuntimeError(f"download failed for {url}: {last_error}")


def resize(source: Path, destination: Path, size: int, quality: int) -> int:
    with Image.open(source) as image:
        image.load()
        image = image.convert("RGBA")
        image.thumbnail((size, size), Image.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, "WEBP", quality=quality, method=6)
    return destination.stat().st_size


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_manifest(args.manifest)
    ids = species_ids(args.data)
    check_coverage(config, ids)

    asset_version = config["asset_version"]
    size = int(config["size"])
    quality = int(config["quality"])
    commit = config["source"]["commit"]
    base = CDN.format(commit=commit)

    existing = current_build(args.out, asset_version, config)
    if existing and not args.force:
        total = sum(existing["files"].values())
        print(
            f"build_web_illustrations: {len(existing['files'])} images "
            f"up to date ({total / 1_000_000:.1f} MB) in {args.out / asset_version}"
        )
        return 0

    cache = args.cache / commit
    jobs = max(1, args.jobs)
    errors: list[str] = []
    sizes: dict[str, int] = {}
    done = 0
    lock = threading.Lock()

    def produce(species_id: str) -> tuple[str, int]:
        sticker = config["stickers"][species_id]
        cached = cache / sticker
        if not cached.is_file() or cached.stat().st_size == 0:
            fetch(base + sticker, cached)
        destination = output_path(args.out, asset_version, species_id)
        return species_id, resize(cached, destination, size, quality)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(produce, species_id): species_id
            for species_id in ids
        }
        for future in as_completed(futures):
            species_id = futures[future]
            try:
                name, bytes_written = future.result()
                with lock:
                    sizes[name] = bytes_written
                    done += 1
                    if done % 50 == 0 or done == len(ids):
                        print(f"build_web_illustrations: {done}/{len(ids)}", flush=True)
            except Exception as exc:  # noqa: BLE001 - report per image
                with lock:
                    errors.append(f"{species_id}: {exc}")

    if errors:
        for error in errors[:10]:
            print(error)
        raise SystemExit(
            f"build_web_illustrations: {len(errors)} images failed"
        )

    if len(sizes) != len(ids):
        raise SystemExit(
            "build_web_illustrations: "
            f"expected {len(ids)} images, wrote {len(sizes)}"
        )

    document = {
        "asset_version": asset_version,
        "source_commit": commit,
        "source_data_version": config["source"].get("data_version"),
        "size": size,
        "quality": quality,
        "count": len(sizes),
        "files": dict(sorted(sizes.items())),
    }
    manifest_path = build_manifest_path(args.out, asset_version)
    manifest_path.write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )
    total = sum(sizes.values())
    print(
        f"build_web_illustrations: wrote {len(sizes)} images "
        f"({total / 1_000_000:.1f} MB) to {args.out / asset_version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
