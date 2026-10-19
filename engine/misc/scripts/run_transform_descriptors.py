"""Compare raster transform-buffer replacement captures, with Vulkan validation.

This is a correctness fixture, not a game FPS qualification.
"""

import argparse
import array
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--validation-layer", type=Path, required=True)
    parser.add_argument("--expected-gpu", required=True, help="Required renderer adapter text")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output directory; preserve previous evidence")
    if not (args.validation_layer / "VkLayer_khronos_validation.json").is_file():
        parser.error("Vulkan validation layer is missing")
    source = Path(__file__).with_name("probe_transform_descriptors.gd")
    args.output.mkdir(parents=True)
    snapshot = args.output / "probe.source.gd"
    snapshot.write_bytes(source.read_bytes())
    env = os.environ.copy()
    env.update(
        VK_LAYER_PATH=str(args.validation_layer.resolve()),
        VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation",
        VK_VALIDATION_VALIDATE_SYNC="true",
    )
    report = {
        "passed": False,
        "performance_acceptance": False,
        "probe_sha256": digest(snapshot),
        "runs": [],
        "comparisons": [],
    }
    manifest = args.output / "manifest.json"
    try:
        for label, binary in [("reference", args.reference), ("candidate", args.candidate)]:
            runtime = args.output / (label + "-runtime")
            runtime.mkdir()
            (runtime / ".godot").mkdir()
            # A registered main loop also works in templates that disable CLI
            # script/path overrides. No editor import or game assets are needed.
            (runtime / ".godot/global_script_class_cache.cfg").write_text(
                'list=[{"base":"SceneTree","class":"TransformDescriptorProbe",'
                '"is_abstract":false,"is_tool":false,"language":"GDScript","path":"res://probe.gd"}]\n'
            )
            # Isolate from an adjacent game PCK and freeze the exact executable/DLLs.
            shutil.copy2(binary, runtime / "engine.exe")
            libraries = []
            for library in sorted(binary.parent.glob("*.dll")):
                shutil.copy2(library, runtime / library.name)
                libraries.append({"name": library.name, "sha256": digest(library)})
            for thread in ["safe", "separate"]:
                folder = args.output / f"{label}-{thread}"
                project = folder / "project"
                project.mkdir(parents=True)
                shutil.copy2(snapshot, project / "probe.gd")
                (project / "project.godot").write_text(
                    'config_version=5\n[application]\nconfig/name="Transform descriptor fixture"\n'
                    'run/main_loop_type="TransformDescriptorProbe"\nrun/main_scene="res://empty.tscn"\n'
                    "[display]\nwindow/size/viewport_width=640\nwindow/size/viewport_height=480\n"
                    '[rendering]\nrenderer/rendering_method="forward_plus"\n'
                    'rendering_device/driver.windows="vulkan"\n'
                    f'streamline/project_id="{uuid.uuid4()}"\n'
                )
                # Release templates can disable --path; use an isolated adjacent
                # project for both binaries instead of requiring a special build.
                shutil.copy2(project / "project.godot", runtime / "project.godot")
                shutil.copy2(snapshot, runtime / "probe.gd")
                (runtime / "empty.tscn").write_text('[gd_scene format=3]\n[node name="Empty" type="Node"]\n')
                command = [
                    str((runtime / "engine.exe").resolve()),
                    "--gpu-index",
                    "0",
                    "--render-thread",
                    thread,
                    "--gpu-validation",
                    "--fixed-fps",
                    "60",
                    "--",
                    "--output=" + str((folder / "capture").resolve()),
                ]
                with (folder / "run.log").open("w") as log:
                    result = subprocess.run(
                        command,
                        cwd=runtime,
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=180,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                text = (folder / "run.log").read_text(errors="replace")
                if (
                    result.returncode
                    or re.search(r"ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit|Resources still in use", text)
                    or "TRANSFORM_DESCRIPTORS_CAPTURED phases=4" not in text
                    or not re.search(r"^Vulkan[^\n]*" + re.escape(args.expected_gpu), text, re.M)
                    or not re.search(r"VK_LAYER_KHRONOS_validation|VkLayer_khronos_validation\.dll", text, re.I)
                ):
                    raise ValueError(f"Rejected fixture: {label}-{thread}; inspect its log")
                report["runs"].append({
                    "label": label,
                    "thread": thread,
                    "engine_sha256": digest(runtime / "engine.exe"),
                    "runtime": libraries,
                })
        for thread in ["safe", "separate"]:
            for phase in range(4):
                values = []
                hashes = []
                for label in ["reference", "candidate"]:
                    path = args.output / f"{label}-{thread}/capture/phase{phase}.rgba32f"
                    raw = path.read_bytes()
                    if len(raw) != 640 * 480 * 16:
                        raise ValueError("Unexpected HDR payload length")
                    pixels = array.array("f", raw)
                    if not all(math.isfinite(value) for value in pixels):
                        raise ValueError("Non-finite HDR output")
                    values.append(pixels)
                    hashes.append(digest(path))
                error = max(abs(a - b) for a, b in zip(*values))
                if error > 0.0005:
                    raise ValueError(f"HDR mismatch {thread} phase {phase}: {error}")
                report["comparisons"].append({
                    "thread": thread,
                    "phase": phase,
                    "max_abs_error": error,
                    "sha256": hashes,
                })
            paths = [args.output / f"candidate-{thread}/capture/phase{phase}.rgba32f" for phase in range(4)]
            if len({digest(path) for path in paths}) != 4:
                raise ValueError("Buffer/pose changes did not change the captured image")
        report["passed"] = True
    finally:
        manifest.write_text(json.dumps(report, indent=2))
    print(json.dumps({"passed": True, "comparisons": len(report["comparisons"])}))


if __name__ == "__main__":
    main()
