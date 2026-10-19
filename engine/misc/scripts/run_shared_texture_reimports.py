"""Run a fresh, headless editor fixture for duplicate/UID image imports.

No application assets, GPU work or visual/performance acceptance is involved.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import zlib


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image(path, color):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    pixels = b"".join(b"\0" + bytes((*color, 255)) * 16 for _ in range(16))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Use a fresh output directory; preserve existing evidence")
    engine = args.engine.resolve()
    binary = engine.with_name(engine.name.replace(".console.exe", ".exe"))
    source = Path(__file__).with_name("probe_shared_texture_reimports.gd")
    frozen = {str(path): digest(path) for path in [engine, binary, source, Path(__file__)]}
    project = output / "project"
    plugin = project / "addons/probe"
    plugin.mkdir(parents=True)
    (project / "project.godot").write_text('''config_version=5
[application]
config/name="Shared texture import regression"
[editor]
import/use_multiple_threads=true
[editor_plugins]
enabled=PackedStringArray("res://addons/probe/plugin.cfg")
[rendering]
renderer/rendering_method="gl_compatibility"
''', encoding="utf8")
    (plugin / "plugin.cfg").write_text('''[plugin]
name="Shared texture reimport regression"
description="Headless editor scheduling fixture"
author="Engine integration tests"
version="1.0"
script="plugin.gd"
''', encoding="utf8")
    shutil.copyfile(source, plugin / "plugin.gd")
    image(project / "shared.png", (40, 80, 120))
    image(project / "second.png", (160, 100, 20))
    command = [str(engine), "--headless", "--editor", "--path", str(project)]
    with (output / "editor.log").open("w", encoding="utf8") as stream:
        completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
    log = (output / "editor.log").read_text(encoding="utf8", errors="replace")
    report_path = project / "result.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    unchanged = all(digest(Path(path)) == value for path, value in frozen.items())
    clean = not re.search(r"ERROR:|SCRIPT ERROR:|ObjectDB.*leaked at exit|Resources still in use", log)
    passed = completed.returncode == 0 and report.get("passed", False) and unchanged and clean
    manifest = {"passed": passed, "exit_code": completed.returncode, "unchanged": unchanged,
                "clean_log": clean, "inputs": frozen, "command": command, "result": report,
                "visual_quality_accepted": False, "performance_accepted": False}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"passed": passed, "exit_code": completed.returncode, "report": str(output / "manifest.json")}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
