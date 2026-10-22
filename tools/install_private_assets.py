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
    weapons = json.loads((GAME.parent / 'data/weapons/catalog.json').read_text(encoding='utf-8'))['weapons']
    for weapon in weapons.values():
        family = weapon['animation_family']
        for pose in ['idle','hit_reaction','aim_level','aim_up30','aim_down30']:
            if f'{family}/{pose}' not in manifest:
                raise ValueError(f'Animation manifest omits required runtime pose: {family}/{pose}')
    licensed_audio = set(audio_files())
    cues = json.loads((GAME.parent / 'data/audio/cues.json').read_text(encoding='utf-8'))
    for cue in cues.values():
        asset = cue.get('asset','')
        if asset.startswith('weapons/') and f'audio/{asset}.wav' not in licensed_audio:
            raise ValueError(f'Audio catalog omits required runtime weapon cue: {asset}')
    return (["animations/manifest.json"] + ["animations/" + name for name in clip_files(manifest)] +
            sorted(licensed_audio))


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
    required_files()
    prepare(GAME / "animations")
    recipe = json.loads((ROOT / "library/sounds/epidemic_manifest.json").read_text(encoding="utf-8"))
    hashes = {entry["file"].removeprefix("game/assets/"):entry["pcm_sha256"] for entry in recipe["game"]}
    catalog = json.loads((GAME / "audio/catalog.json").read_text(encoding="utf-8"))
    for item in catalog.values():
        if item.get('provider','').startswith('User-supplied'):
            digest = item.get('pcm_sha256','')
            if not re.fullmatch(r'[0-9a-f]{64}',digest):
                raise ValueError('User-supplied audio requires a pinned PCM checksum')
            hashes[item['file'].removeprefix('res://assets/')] = digest
    for name in audio_files():
        path = GAME / name
        if not path.is_file():
            raise ValueError(f"Missing {name}. See docs/ASSET_SETUP.md.")
        pcm,channels,width,rate = read_pcm(path)
        if (channels,width,rate)!=(1,2,48000) or hashlib.sha256(pcm).hexdigest()!=hashes.get(name):
            raise ValueError(f"Game-cue PCM differs from the verified recipe: {name}")
    print("PASS local licensed game assets")


def install_archive(archive, digest):
    digest = digest.strip()
    if not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('PRIVATE_GAME_ASSETS_SHA256 must contain only the 64 hexadecimal SHA-256 characters, without a filename or command output')
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != digest.lower():
        raise ValueError('Private asset archive checksum mismatch. Downloaded ZIP SHA-256: ' + actual +
                         '. Verify the R2 object and update PRIVATE_GAME_ASSETS_SHA256 to the intended archive hash')
    parent = ROOT / '.local'
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as scratch:
        folder = Path(scratch)
        with zipfile.ZipFile(archive) as zipped:
            required = required_files()
            missing = [name for name in required if name not in zipped.namelist()]
            if missing:
                raise ValueError('Private ZIP is missing required entries: ' + ', '.join(missing[:5]) +
                                 '. ZIP root must contain animations/ and audio/; see docs/ASSET_SETUP.md')
            for name in required:
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
    except ValueError as error:
        raise SystemExit(f"Private asset setup failed: {error}. See docs/ASSET_SETUP.md.") from None
    except zipfile.BadZipFile:
        raise SystemExit("Private asset setup failed: ZIP is invalid or corrupt. Download or rebuild the bundle.") from None
    except (OSError, KeyError) as error:
        raise SystemExit(f"Private asset setup failed: {type(error).__name__} while reading or installing required files. See docs/ASSET_SETUP.md.") from None
