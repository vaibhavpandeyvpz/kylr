"""Validate GPU viewport snapshots against immediate Image readback controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

import numpy as np
from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--validation-layers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render-thread", choices=["safe", "separate"], default="safe")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / "project"
    project.mkdir()
    source = Path(__file__).resolve().parent
    names = ["gpu_frame_capture.gd", "probe_gpu_frame_capture.gd"]
    hashes = {name: digest(source/name) for name in names}
    for name in names:
        shutil.copy2(source/name, project/name)
    (project/"project.godot").write_text('''config_version=5
[application]
config/name="GPU viewport snapshot diagnostic"
[display]
window/size/viewport_width=64
window/size/viewport_height=64
window/vsync/vsync_mode=0
[rendering]
renderer/rendering_method="forward_plus"
rendering_device/driver.windows="vulkan"
driver/threads/thread_model=1
streamline/project_id="%s"
''' % uuid.uuid4())
    env = os.environ.copy()
    env["VK_LAYER_PATH"] = str(args.validation_layers.resolve())
    env["VK_INSTANCE_LAYERS"] = "VK_LAYER_KHRONOS_validation"
    env["VK_VALIDATION_VALIDATE_SYNC"] = "true"
    env["VK_LAYER_VALIDATE_SYNC"] = "1"
    env.pop("VK_LAYER_ENABLES", None)
    engine = args.engine.resolve()
    renderer = engine.with_name(engine.name.removesuffix(".console.exe")+".exe") if engine.name.endswith(".console.exe") else engine
    binary = digest(renderer)
    command = [str(engine), "--path", str(project), "--gpu-validation", "--render-thread", args.render_thread,
               "--script", "res://probe_gpu_frame_capture.gd", "--", "--output="+str(output/"report.json")]
    with (output/"engine.log").open("w", encoding="utf-8") as log:
        run = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
    text = (output/"engine.log").read_text(errors="replace")
    errors = re.findall(r"(?im)^.*(?:ERROR:|SCRIPT ERROR:|VUID-|SYNC-HAZARD|ObjectDB instances were leaked|Resources still in use).*$", text)
    sync = bool(re.search(r"Current Validation Enabled:[\s\S]{0,300}- Synchronization", text))
    stable = digest(renderer) == binary and all(digest(source/name) == value and digest(project/name) == value for name, value in hashes.items())
    path = output/"report.json"
    report = json.loads(path.read_text()) if path.exists() else {}
    coverage = ([row["case"] for row in report.get("cases", [])] == ["paired", "deferred"])
    pixels_equal = False
    if coverage and run.returncode == 0 and not errors:
        pixels_equal = all(np.array_equal(np.asarray(Image.open(output/f'paired-{i:02d}.png')),
                                         np.asarray(Image.open(output/f'deferred-{i:02d}.png'))) for i in range(8))
    passed = bool(run.returncode == 0 and not errors and sync and stable and report.get("passed") and coverage
                  and pixels_equal and report.get("repeated_release") and report.get("helper_sha256") == hashes["gpu_frame_capture.gd"]
                  and report.get("probe_sha256") == hashes["probe_gpu_frame_capture.gd"]
                  and report.get("engine_sha256", "").lower() == binary.lower()
                  and all(row["passed"] and row["matches"] == [True]*8 and row["capture"]["copied"] == 8
                          for row in report.get("cases", []))
                  and not report["cases"][1]["readback_during_sequence"])
    result = {"passed": passed, "scope": __doc__, "command": command, "engine_exit_code": run.returncode,
              "engine_sha256": binary, "render_thread": args.render_thread, "source_hashes": hashes,
              "sources_unchanged": stable, "synchronization_validation_enabled": sync, "errors": errors,
              "paired_deferred_pngs_equal": pixels_equal, "performance_acceptance": False, "quality_acceptance": False}
    (output/"verification.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({key: result[key] for key in ["passed", "engine_exit_code", "sources_unchanged", "errors"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
