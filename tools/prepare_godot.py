"""Install checksum-pinned official Godot binaries; requires only Python's stdlib."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile


def install(platform, output, templates=False):
    manifest = json.loads(Path(__file__).with_name("godot-release.json").read_text())
    release = manifest["release"]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    def extract(name, members, destination):
        url = f"https://github.com/godotengine/godot-builds/releases/download/{release}/{name}"
        with tempfile.TemporaryDirectory(prefix="godot-download-") as temporary:
            archive = Path(temporary) / name
            print(f"Downloading {name}", flush=True)
            urllib.request.urlretrieve(url, archive)
            with archive.open("rb") as source:
                digest = hashlib.file_digest(source, "sha512").hexdigest()
            if digest != manifest["files"][name]:
                raise ValueError(f"Official archive checksum mismatch: {name}")
            destination.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as package:
                for member, target in members.items():
                    with package.open(member) as source, (destination / target).open("wb") as result:
                        shutil.copyfileobj(source, result)

    if platform == "windows":
        extract(f"Godot_v{release}_win64.exe.zip", {
            f"Godot_v{release}_win64.exe": "godot.exe",
            f"Godot_v{release}_win64_console.exe": "godot_console.exe",
        }, output)
    else:
        extract(f"Godot_v{release}_linux.x86_64.zip", {
            f"Godot_v{release}_linux.x86_64": "godot",
        }, output)
        (output / "godot").chmod(0o755)
    if templates:
        data = Path(os.environ.get("APPDATA", "")) if platform == "windows" else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        destination = data / ("Godot" if platform == "windows" else "godot") / "export_templates" / manifest["version"]
        names = ["version.txt", "windows_debug_x86_64.exe", "windows_release_x86_64.exe"] if platform == "windows" else ["version.txt", "linux_debug.x86_64", "linux_release.x86_64"]
        extract(f"Godot_v{release}_export_templates.tpz", {f"templates/{name}": name for name in names}, destination)
        if (destination / "version.txt").read_text().strip() != manifest["version"]:
            raise ValueError("Export template version mismatch")
    print(f"Installed official Godot {manifest['version']} in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["windows", "linux"], required=True)
    parser.add_argument("--output", default=".local/godot")
    parser.add_argument("--templates", action="store_true")
    arguments = parser.parse_args()
    install(arguments.platform, arguments.output, arguments.templates)
