"""Check analytical particle occlusion against raster and an old-path control."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def compare(root):
    manifest = json.loads((root / "manifest.json").read_text())
    if not manifest.get("captured") or not manifest.get("validation"):
        raise ValueError("Missing completed synchronization-validated captures")
    labels = {"opaque", "cutout", "instance_fade", "opaque_cover", "transparent_front"}
    modes = {}
    inputs = [root / "manifest.json"]
    for run in manifest["runs"]:
        mode = run["mode"]
        if mode in modes or run["native_ack"] != (mode == "rt-candidate"):
            raise ValueError("Duplicate mode or incorrect native feature acknowledgement")
        folder = root / mode
        script = folder / "project/probe.gd"
        project = folder / "project/project.godot"
        if hashlib.sha256(script.read_bytes()).hexdigest().upper() != manifest["source_sha256"].upper():
            raise ValueError("Copied fixture source does not match the captured source hash")
        report_path = folder / "capture/report.json"
        report = json.loads(report_path.read_text())
        if report["cases"] != run["cases"]:
            raise ValueError("Capture report changed after the run")
        rows = {row["case"]: row for row in report["cases"]}
        if len(rows) != 5 or set(rows) != labels:
            raise ValueError("Incomplete overlap cases")
        stdout, stderr = folder / "stdout.log", folder / "stderr.log"
        logs = stdout.read_text(errors="replace") + stderr.read_text(errors="replace")
        if re.search(r"^ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit|OpTypeForwardPointer", logs, re.M):
            raise ValueError("Renderer or synchronization diagnostics failed")
        if not re.search(r"VK_LAYER_KHRONOS_validation|VkLayer_khronos_validation\.dll", logs, re.I):
            raise ValueError("Missing native validation-layer evidence")
        for row in rows.values():
            if mode != "raster":
                rr = row.get("reconstruction", {})
                if rr.get("backend") != "DLSS" or not rr.get("viewport_renderer") or not rr.get("evaluation_succeeded") or rr.get("frames", 0) < 60:
                    raise ValueError("Missing successful native RR evaluations")
            inputs.append(folder / "capture" / (row["case"] + ".png"))
        inputs.extend([script, project, report_path, stdout, stderr])
        modes[mode] = rows
    if set(modes) != {"raster", "rt-control", "rt-candidate"}:
        raise ValueError("Missing raster, previous-path or candidate capture")
    reference, control, candidate = [modes[m] for m in ("raster", "rt-control", "rt-candidate")]
    if not (reference["opaque"]["center"][0] > 0.75 and reference["opaque"]["center"][2] < 0.3):
        raise ValueError("Raster reference did not show the near red particle")
    if not (reference["cutout"]["left"][2] > 0.75 and reference["cutout"]["right"][0] > 0.75):
        raise ValueError("Raster reference did not exercise the cutout hole")
    if not (reference["opaque_cover"]["center"][1] > 0.75 and reference["transparent_front"]["center"][0] > 0.5 and reference["transparent_front"]["center"][1] > 0.5):
        raise ValueError("Raster reference did not exercise foreground cover and blending")
    if not (control["opaque"]["center"][2] > 0.75 and control["cutout"]["right"][2] > 0.75):
        raise ValueError("Previous-path control did not reproduce the far-particle overwrite")
    errors = {}
    # This checks material ordering, not byte-identical reconstruction. A small
    # color tolerance permits RR's subpixel reconstruction of the raster input.
    tolerance = 0.03
    for label in sorted(labels):
        error = max(abs(a-b) for region in ("center", "left", "right")
                    for a, b in zip(reference[label][region], candidate[label][region]))
        errors[label] = error
        if error > tolerance:
            raise ValueError("Candidate differs from raster reference: " + label)
    for label in ("instance_fade", "opaque_cover"):
        error = max(abs(a-b) for region in ("center", "left", "right")
                    for a, b in zip(control[label][region], candidate[label][region]))
        if error > tolerance:
            raise ValueError("Excluded/covered material changed: " + label)
    return {"passed": True, "performance_acceptance": False,
            "scope": "static overlap, cutout, instance fading and foreground cover; not motion or full-game qualification",
            "old_path_failure_reproduced": True, "native_rr_verified": True,
            "max_rgb_error_by_case": errors, "color_tolerance": tolerance,
            "input_sha256": {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose fresh comparison output")
    result = compare(args.capture_root)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key:value for key,value in result.items() if key != "input_sha256"}))
