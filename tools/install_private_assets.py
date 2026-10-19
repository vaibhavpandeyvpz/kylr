"""Restore separately licensed game assets from a private, checksummed bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import re
import zipfile

from install_animations import clip_files, prepare, ROOT
from audio_pcm import read_pcm

GAME = ROOT / "game/assets"


def audio_files():
    catalog = json.loads((GAME / "audio/catalog.json").read_text(encoding="utf-8"))
    files = set()
    for item in catalog.values():
        if item.get("provider", "").startswith(("User-supplied", "Epidemic Sound")):
            files.update(item.get("files", [item["file"]] if "file" in item else []))
    result = []
    for name in sorted(files):
        if not name.startswith("res://assets/audio/") or ".." in Path(name).parts:
            raise ValueError("Invalid licensed-audio path in catalog")
        result.append(name.removeprefix("res://assets/"))
    return result


def required_files():
    manifest = json.loads((GAME / "animations/manifest.json").read_text(encoding="utf-8"))
    return (["animations/manifest.json"] + ["animations/" + name for name in clip_files(manifest)] +
            audio_files())


def install(source):
    expected = json.loads((GAME / "animations/manifest.json").read_text(encoding="utf-8"))
    supplied = json.loads((source / "animations/manifest.json").read_text(encoding="utf-8"))
    if supplied != expected:
        raise ValueError("Private animation manifest differs from this checkout")
    for name in required_files():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError(f"Missing private asset: {name}")
    prepare(source / "animations")
    prepare(source / "animations", install=True)
    for name in audio_files():
        target = GAME / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if (source / name).resolve() != target.resolve():
            shutil.copyfile(source / name, target)
    check()


def check():
    prepare(GAME / "animations")
    recipe = json.loads((ROOT / "library/sounds/epidemic_manifest.json").read_text(encoding="utf-8"))
    hashes = {entry["file"].removeprefix("game/assets/"):entry["pcm_sha256"] for entry in recipe["game"]}
    for name in audio_files():
        path = GAME / name
        if not path.is_file():
            raise ValueError(f"Missing {name}. See docs/ASSET_SETUP.md.")
        pcm,channels,width,rate = read_pcm(path)
        if (channels,width,rate)!=(1,2,48000) or hashlib.sha256(pcm).hexdigest()!=hashes.get(name):
            raise ValueError(f"Game-cue PCM differs from the verified recipe: {name}")
    print("PASS local licensed game assets")


def install_archive(archive, digest):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('Supply the private asset SHA-256 pin')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest.lower():
        raise ValueError('Private asset archive checksum mismatch')
    parent = ROOT / 'engine/.local'
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as scratch:
        folder = Path(scratch)
        with zipfile.ZipFile(archive) as zipped:
            for name in required_files():
                # Only this checkout's allowlisted paths can leave the archive.
                target = folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(name) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
        install(folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--source", type=Path, help="Prepared private folder with animations/, audio/")
    mode.add_argument("--archive", type=Path, help="Prepared private ZIP downloaded with the AWS CLI")
    parser.add_argument("--sha256", default=os.environ.get('PRIVATE_GAME_ASSETS_SHA256', ''),
                        help="Required archive pin; otherwise use PRIVATE_GAME_ASSETS_SHA256")
    args = parser.parse_args()
    try:
        if args.check:
            check()
        elif args.source:
            install(args.source.resolve())
        else:
            install_archive(args.archive.resolve(), args.sha256)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile):
        raise SystemExit("Private asset setup failed. Check the configured bundle, checksum and docs/ASSET_SETUP.md.") from None
