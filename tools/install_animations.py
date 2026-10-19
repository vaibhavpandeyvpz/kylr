"""Check Mixamo downloads or install locally retargeted clips into the game."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "library/animations/downloads.json"
SOURCES = ROOT / "library/animations/source"
TARGET = ROOT / "game/assets/animations"


def relative_file(directory, name):
    path = (directory / name).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError(f"Animation path escapes its folder: {name}")
    return path


def check_sources():
    spec = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
    missing = []
    for archive, members in spec["packs"].items():
        path = SOURCES / archive
        if not path.is_file():
            missing.append(archive)
            continue
        with zipfile.ZipFile(path) as contents:
            names = {Path(name).name for name in contents.namelist()}
        missing.extend(f"{archive} :: {name}" for name in members if name not in names)
    missing.extend(name for name in spec["clips"] if not (SOURCES / name).is_file())
    if missing:
        raise ValueError("Missing Mixamo sources:\n  " + "\n  ".join(missing) +
                         "\nSee docs/ASSET_SETUP.md for downloads and folder layout.")
    print("PASS Mixamo source packs, required members and individual clips")


def clip_files(manifest):
    files = set()
    for key, entry in manifest.items():
        for field in ("file", "weapon_file"):
            if field in entry:
                name = entry[field]
                if not name.endswith(".glb") or not name.startswith(("tensor/", "weapons/")) or ".." in Path(name).parts or Path(name).is_absolute():
                    raise ValueError(f"Unexpected animation file for {key}: {name}")
                files.add(name)
    if not files:
        raise ValueError("Animation manifest has no clips")
    return sorted(files)


def prepare(source, install=False):
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Missing {manifest_path}. See docs/ASSET_SETUP.md.")
    authored = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = json.loads((TARGET / "manifest.json").read_text(encoding="utf-8")) if install else authored
    if install:
        missing = set(manifest)-set(authored)
        if missing:
            raise ValueError(f"Retarget output lacks required clips: {sorted(missing)}")
        for key,entry in manifest.items():
            for field in ("file","weapon_file"):
                if field in entry and authored[key].get(field) != entry[field]:
                    raise ValueError(f"Retarget output changes the required path for {key}")
    files = clip_files(manifest)
    # Validate everything before copying any files.
    for name in files:
        path = relative_file(source, name)
        if not path.is_file():
            raise ValueError(f"Missing animation: {path}. Run the complete retarget pass.")
        with path.open("rb") as stream:
            if stream.read(4) != b"glTF":
                raise ValueError(f"Invalid GLB animation: {path}")
    if install:
        for name in files:
            target = relative_file(TARGET, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if (source / name).resolve() != target:
                shutil.copyfile(source / name, target)
    print(f"PASS {'installed' if install else 'local'} animation library: {len(manifest)} clips, {len(files)} GLBs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-sources", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--source", type=Path, help="Complete retarget output folder")
    args = parser.parse_args()
    try:
        if args.check_sources:
            check_sources()
        else:
            prepare(args.source.resolve() if args.source else TARGET, install=args.source is not None)
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Animations: {error}\n")
