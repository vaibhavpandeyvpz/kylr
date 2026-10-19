"""Validate actual SDK feature queries/evaluations across same-viewport switches."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
from verify_rt_temporal_edges import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--validation-layers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path,
                        help="Pinned production runtime manifest for isolated SDK qualification")
    parser.add_argument("--sr-preset", choices=("default","K","L","M"), default="default",
                        help="Diagnostic model isolation; never quality or performance acceptance")
    parser.add_argument("--rr-preset", choices=("default","D","E"), default="default",
                        help="Requested RR model for the feature-switching comparison")
    parser.add_argument("--resolution", choices=("640x360","1920x1080"), default="640x360")
    args = parser.parse_args()
    width,height = map(int,args.resolution.split("x"))
    validation_path = args.validation_layers.resolve()
    if not (validation_path / "VkLayer_khronos_validation.json").is_file():
        parser.error("--validation-layers must name the directory containing VkLayer_khronos_validation.json")
    if args.output.exists():
        parser.error("Use a fresh output directory")
    output = args.output.resolve()
    project = output / "project"
    project.mkdir(parents=True)
    engine = args.engine.resolve()
    engine = engine.with_name(engine.name.replace(".console.exe", ".exe"))
    probe = Path(__file__).with_name("probe_dlss_feature_lifecycle.gd")
    sdk_path = (args.runtime_manifest or
                Path(__file__).resolve().parents[2] / "drivers/streamline/runtime_manifest.json").resolve()
    sdk = json.loads(sdk_path.read_text())
    if sdk.get("runtime_flavor") != "production" or len(sdk["files"]) != 12:
        raise ValueError("Missing pinned production runtime")
    inputs = [engine, probe, Path(__file__), sdk_path, Path(__file__).with_name("verify_rt_temporal_edges.py"),
              validation_path / "VkLayer_khronos_validation.json",
              validation_path / "VkLayer_khronos_validation.dll"]
    for item in sdk["files"]:
        path = engine.parent / item["name"]
        if digest(path) != item["sha256"]:
            raise ValueError("Runtime mismatch: "+item["name"])
        inputs.append(path)
    hashes = {str(p.resolve()):digest(p) for p in inputs}
    shutil.copyfile(probe, project / "probe.gd")
    shutil.copyfile(Path(__file__), output / "verifier.source.py")
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="DLSS feature lifecycle"\n'
        f'[display]\nwindow/size/viewport_width={width}\nwindow/size/viewport_height={height}\n[rendering]\n'
        'renderer/rendering_method="forward_plus"\nrendering_device/driver.windows="vulkan"\n'
        'streamline/project_id="'+str(uuid.uuid4())+'"\n')
    env = os.environ.copy()
    env.pop("GODOT_DLSS_RENDERER_EXPOSURE",None)
    for name in ("GODOT_DLSS_RR_PARTICLE_HINT","GODOT_DLSS_RR_OPAQUE_PARTICLE_GUIDES","GODOT_DLSS_RR_TRANSPARENCY_LAYER",
                 "GODOT_GPU_PROFILE_ALPHA_FILTER","GODOT_GPU_PROFILE_ALPHA_MASK"):
        env.pop(name,None)
    env.update(GODOT_DLSS_DIAGNOSTICS="1",VK_LAYER_PATH=str(validation_path),
               VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation",VK_VALIDATION_VALIDATE_SYNC="true")
    manifest = {"passed":False,"quality_acceptance":False,"performance_acceptance":False,
                "sdk_version":sdk["sdk_version"],
                "sr_preset":args.sr_preset,"rr_preset":args.rr_preset,"output_size":[width,height],"input_sha256":hashes}
    try:
        with (output/"stdout.log").open("w") as stdout, (output/"stderr.log").open("w") as stderr:
            process = subprocess.run([str(engine),"--verbose","--path",str(project),"--fixed-fps","60","--render-thread","safe",
                "--gpu-validation","--script","res://probe.gd","--","--output="+str(output/"capture"),
                "--sr-preset="+args.sr_preset,"--rr-preset="+args.rr_preset,"--resolution="+args.resolution],
                env=env,stdout=stdout,stderr=stderr,timeout=660,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        log = (output/"stdout.log").read_text(errors="replace")+(output/"stderr.log").read_text(errors="replace")
        manifest["exit_code"] = process.returncode
        manifest["capture_completed"] = "DLSS_FEATURE_LIFECYCLE_PASS phases=4" in log
        if "DLSS_LIFECYCLE_SR_PRESET "+args.sr_preset not in log:
            raise ValueError("Requested SR preset was not configured")
        if "DLSS_LIFECYCLE_RR_PRESET "+args.rr_preset not in log:
            raise ValueError("Requested RR preset was not configured")
        validation_errors = re.findall(r"Message Id Name: ((?:VUID-|SYNC-HAZARD)[\w-]+)",log)
        manifest["validation_error_counts"] = {
            name:validation_errors.count(name) for name in sorted(set(validation_errors))
        }
        report_path = output/"capture/report.json"
        if report_path.is_file():
            manifest["phases"] = json.loads(report_path.read_text())["rows"]
        if process.returncode or re.search(r"ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit|Resources still in use",log):
            raise ValueError("Lifecycle capture failed")
        if "DLSS_FEATURE_LIFECYCLE_PASS phases=4" not in log or "VK_LAYER_KHRONOS_validation" not in log:
            raise ValueError("Missing validated completion")
        phases = re.split(r"DLSS_LIFECYCLE_PHASE ",log)[1:]
        if len(phases)!=4:
            raise ValueError("Incomplete phases")
        for text, feature in zip(phases,["SR","RR","SR","RR"]):
            if f"DLSS_OPTIMAL_SETTINGS feature={feature}" not in text or f"DLSS_EVALUATION feature={feature} succeeded=1" not in text:
                raise ValueError("Missing feature-specific query and actual SDK evaluation: "+feature)
        report = json.loads((output/"capture/report.json").read_text())
        if report.get("sr_preset") != args.sr_preset or report.get("rr_preset") != args.rr_preset:
            raise ValueError("Capture model requests differ from the configured comparison")
        if report.get("output_size") != [width,height]:
            raise ValueError("Output dimensions differ from requested dimensions")
        if len(report["rows"])!=4 or len({r["viewport"] for r in report["rows"]})!=1:
            raise ValueError("Viewport continuity failed")
        if any(digest(Path(p))!=h for p,h in hashes.items()):
            raise ValueError("Inputs changed during capture")
        manifest["passed"] = True
        manifest["phases"] = report["rows"]
    except Exception as error:
        manifest["error"] = str(error)
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k!="input_sha256"}),flush=True)
    raise SystemExit(0 if manifest["passed"] else 1)


if __name__=="__main__":
    main()
