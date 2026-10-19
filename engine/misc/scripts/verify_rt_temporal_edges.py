"""Measure vacated silhouette pixels, with raster and submitted-ghost controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(folder, output_size, requested_scale=None, super_resolution=False, require_inputs=False):
    report = json.loads((folder / "capture/report.json").read_text())
    if report.get("output_size") != output_size:
        raise ValueError("Capture output dimensions differ from requested dimensions")
    if report.get("super_resolution",False) != super_resolution:
        raise ValueError("Capture feature differs from requested feature")
    expected_scale = report["scale"] if requested_scale is None else requested_scale
    if report["backend"] == "dlss" and abs(report["scale"]-expected_scale) > .000001:
        raise ValueError("Viewport scale differs from the requested scale")
    rows = {row["case"]: row for row in report["cases"]}
    if not report.get("captured") or set(rows) != {"camera_motion", "object_motion", "particle_motion"}:
        raise ValueError("Incomplete temporal capture")
    result = {}
    for name, row in rows.items():
        samples = row["samples"]
        if len(samples) != 32 or any(s["step"] != i or s["samples"] < 30 for i, s in enumerate(samples)):
            raise ValueError("Incomplete vacated-pixel sampling")
        if not all(s.get("foreground", {}).get("visible") for s in samples):
            raise ValueError("Missing visible foreground: " + name + "; empty output cannot qualify motion quality")
        if require_inputs and any(len(s.get("inputs", [])) != 2 for s in samples):
            raise ValueError("Missing requested input-buffer samples: " + name)
        if any("inputs" in s for s in samples):
            if any(len(s.get("inputs", [])) != 2 for s in samples):
                raise ValueError("Missing requested input-buffer samples")
            depth_error = max(abs(p["depth"]-p["expected_depth"]) for s in samples for p in s["inputs"])
            velocity_error = max(abs(a-b) for s in samples for p in s["inputs"]
                                 for a,b in zip(p["velocity"],p["expected_velocity"]))
            if depth_error > .00001 or velocity_error > .0001:
                raise ValueError("Input-buffer mismatch: " + name + " depth="+str(depth_error)+" velocity="+str(velocity_error))
        if report["backend"] == "dlss":
            before, after = row["before"], row["after"]
            if super_resolution and after.get("feature") != "SR":
                raise ValueError("Missing native SR feature metadata")
            if (after.get("backend") != "DLSS" or not after.get("evaluation_succeeded") or
                    not after.get("viewport_renderer") or after.get("frames", 0)-before.get("frames", 0) < 32 or
                    after.get("resets", 0)-before.get("resets", 0) > 1 or
                    after.get("size") != [round(d*expected_scale) for d in output_size] or
                    after.get("output_size") != output_size):
                raise ValueError("Missing continuous native RR evaluations")
        worst = max(sample["p95_rgb_excess"] for sample in samples)
        result[name] = {"worst_p95_rgb_excess": worst,
                        "worst_pixel_rgb_excess": max(s["max_rgb_excess"] for s in samples),
                        "frames_above_limit": sum(s["p95_rgb_excess"] > .05 for s in samples),
                        "within_limit": worst <= .05}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--validation-layers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, choices=(.45, .5, 1.0), default=.5)
    parser.add_argument("--render-thread", choices=("safe", "separate"), default="safe")
    parser.add_argument("--verbose-engine", action="store_true")
    parser.add_argument("--projection", choices=("perspective", "orthographic"), default="perspective")
    parser.add_argument("--sharpening", type=float)
    parser.add_argument("--capture-inputs", action="store_true")
    parser.add_argument("--resolution", choices=("640x360", "1920x1080"), default="640x360")
    parser.add_argument("--transparency-layer", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--reverse-motion", action="store_true")
    parser.add_argument("--opaque-particle-guides", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ghost-writes-depth", action="store_true")
    parser.add_argument("--rr-preset", choices=("default","D","E"), default="default")
    parser.add_argument("--sr-preset", choices=("default","K","L","M"), default="default")
    parser.add_argument("--super-resolution", action="store_true")
    args = parser.parse_args()
    if not (args.validation_layers.resolve()/"VkLayer_khronos_validation.json").is_file():
        parser.error("--validation-layers must contain VkLayer_khronos_validation.json")
    if args.transparency_layer or args.opaque_particle_guides:
        parser.error("The unqualified transparency-layer and particle-guide renderer experiments have been removed")
    output_size = [int(d) for d in args.resolution.split("x")]
    if args.sharpening is not None and not 0 <= args.sharpening <= 2:
        parser.error("Sharpening must be in [0,2]")
    if args.output.exists():
        parser.error("Use a fresh output directory; preserve prior evidence")
    root = args.output.resolve()
    root.mkdir(parents=True)
    engine = args.engine.resolve()
    real_engine = engine.with_name(engine.name.replace(".console.exe", ".exe"))
    source = Path(__file__).with_name("probe_rt_temporal_edges.gd")
    shutil.copyfile(Path(__file__), root / "verifier.source.py")
    sdk_path = Path(__file__).resolve().parents[2] / "drivers/streamline/runtime_manifest.json"
    sdk = json.loads(sdk_path.read_text())
    if sdk.get("runtime_flavor") != "production" or len(sdk["files"]) != 12:
        raise ValueError("Missing pinned production SDK")
    inputs = [real_engine, source, Path(__file__), sdk_path]
    for item in sdk["files"]:
        path = engine.parent / item["name"]
        if digest(path) != item["sha256"]:
            raise ValueError("SDK runtime hash mismatch: " + item["name"])
        inputs.append(path)
    hashes = {str(p.resolve()): digest(p) for p in inputs}
    environment = os.environ.copy()
    for name in ("GODOT_GPU_PROFILE_ALPHA_FILTER", "GODOT_GPU_PROFILE_ALPHA_MASK",
                 "GODOT_RT_LIGHT_GRID_CAPTURE", "GODOT_RT_OPAQUE_PARTICLE_DEPTH", "GODOT_DLSS_NEGATE_JITTER_AXES",
                 "GODOT_DLSS_RR_GUIDE_AFTER_TRANSPARENCY", "GODOT_DLSS_RR_TRANSPARENCY_LAYER", "GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES", "GODOT_DLSS_RR_PARTICLE_HINT", "GODOT_DLSS_RENDERER_EXPOSURE"):
        environment.pop(name, None)
    environment.update(GODOT_DLSS_DIAGNOSTICS="1", VK_LAYER_PATH=str(args.validation_layers.resolve()),
                       VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation", VK_VALIDATION_VALIDATE_SYNC="true")
    result = {"captured": False, "passed": False, "performance_acceptance": False,
              "full_scene_quality_acceptance": False, "render_thread": args.render_thread,"projection":args.projection,
              "rr_preset":args.rr_preset,
              "sr_preset":args.sr_preset,"super_resolution":args.super_resolution,
              "trail_limit": .05,"output_size":output_size,"reverse_motion":args.reverse_motion,
              "ghost_writes_depth":args.ghost_writes_depth,"sharpening_requested":args.sharpening,"input_sha256": hashes, "runs": {}}
    try:
        for mode in ("raster", "dlss", "dlss-ghost"):
            folder = root / mode
            project = folder / "project"
            project.mkdir(parents=True)
            shutil.copyfile(source, project / "probe.gd")
            (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Temporal edge fixture"\n'
                f'[display]\nwindow/size/viewport_width={output_size[0]}\nwindow/size/viewport_height={output_size[1]}\n[rendering]\n'
                'renderer/rendering_method="forward_plus"\nrendering_device/driver.windows="vulkan"\n'
                'streamline/project_id="' + str(uuid.uuid4()) + '"\n')
            command = [str(real_engine), "--path", str(project), "--fixed-fps", "60",
                       "--render-thread", args.render_thread, "--gpu-validation", "--script", "res://probe.gd", "--",
                       "--backend=" + ("raster" if mode == "raster" else "dlss"),
                       "--scale=" + str(args.scale), "--resolution="+args.resolution, "--projection="+args.projection,
                       "--rr-preset="+args.rr_preset,"--sr-preset="+args.sr_preset,"--output=" + str(folder / "capture")]
            if args.super_resolution:
                command.append("--super-resolution")
            if mode == "dlss-ghost":
                command.append("--inject-ghost")
            if args.reverse_motion:
                command.append("--reverse-motion")
            if args.ghost_writes_depth:
                command.append("--ghost-writes-depth")
            if args.verbose_engine:
                command.insert(1, "--verbose")
            if args.sharpening is not None:
                command.append("--sharpening="+str(args.sharpening))
            if args.capture_inputs and mode != "raster":
                command.append("--capture-inputs")
            with (folder / "stdout.log").open("w") as stdout, (folder / "stderr.log").open("w") as stderr:
                process = subprocess.run(command, env=environment, stdout=stdout, stderr=stderr, timeout=660,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            logs = (folder / "stdout.log").read_text(errors="replace") + (folder / "stderr.log").read_text(errors="replace")
            if process.returncode or re.search(r"ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit|Resources still in use at exit", logs):
                raise ValueError("Capture failed: " + mode)
            if not re.search(r"VK_LAYER_KHRONOS_validation|VkLayer_khronos_validation\.dll", logs, re.I) or "RT_TEMPORAL_EDGES_CAPTURED" not in logs:
                raise ValueError("Missing validated capture completion: " + mode)
            feature="SR" if args.super_resolution else "RR"
            if mode != "raster" and "DLSS_OPTIMAL_SETTINGS feature="+feature not in logs:
                raise ValueError("Missing feature-specific settings query: "+feature)
            if mode != "raster" and "RT_TEMPORAL_SR_PRESET "+args.sr_preset not in logs:
                raise ValueError("Requested SR preset was not configured")
            if mode != "raster" and "RT_TEMPORAL_RR_PRESET "+args.rr_preset not in logs:
                raise ValueError("Requested RR preset was not configured")
            capture_report = json.loads((folder/"capture/report.json").read_text())
            if capture_report.get("rr_preset") != args.rr_preset or capture_report.get("sr_preset") != args.sr_preset:
                raise ValueError("Capture preset differs from requested preset")
            result["runs"][mode] = inspect(folder, output_size, args.scale, args.super_resolution,
                                          require_inputs=args.capture_inputs and mode != "raster")
            print("CAPTURE " + mode + " " + json.dumps(result["runs"][mode]), flush=True)
        if any(digest(Path(name)) != value for name, value in hashes.items()):
            raise ValueError("Fixture inputs changed during capture")
        result["captured"] = True
        if not all(case["within_limit"] for case in result["runs"]["raster"].values()):
            raise ValueError("Raster control failed; inspect the oracle alignment before blaming reconstruction")
        if not all(case["frames_above_limit"] >= 12 for case in result["runs"]["dlss-ghost"].values()):
            raise ValueError("Submitted ghost was not reliably detected")
        result["submitted_ghost_detected"] = True
        result["passed"] = all(case["within_limit"] for case in result["runs"]["dlss"].values())
        if not result["passed"]:
            result["error"] = "DLSS retains color in vacated silhouette pixels; inspect captures"
    except Exception as error:
        result["error"] = str(error)
    (root / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "input_sha256"}), flush=True)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
