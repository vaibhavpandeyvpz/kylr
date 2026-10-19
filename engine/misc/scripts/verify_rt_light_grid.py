"""Run a generic raw-transport/index oracle, including omitted-light controls."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import struct
import subprocess
import uuid


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lights_from_bytes(data, count):
    if len(data) != 64 * 112 or count != 64:
        raise ValueError("Expected the complete 64-light native buffer")
    lights = []
    for index in range(count):
        base = index * 112
        lights.append({"position": struct.unpack_from("<3f", data, base),
                       "type": struct.unpack_from("<I", data, base + 12)[0],
                       "range_squared": struct.unpack_from("<f", data, base + 40)[0]})
    if {light["type"] for light in lights} != {0, 1, 2, 3}:
        raise ValueError("The fixture must exercise all four native light types")
    return lights


def oracle(data, lights, points):
    words = struct.unpack("<" + "I" * (len(data) // 4), data)
    origin = struct.unpack_from("<3f", data)
    inverse_width = struct.unpack_from("<f", data, 12)[0]
    dimensions, cells = words[4:7], words[7]
    if words[10] != 1 or words[11] != len(lights) or math.prod(dimensions) != cells:
        raise ValueError("Invalid active index header")
    if len(words) != 12 + cells * 2 or not math.isfinite(inverse_width) or inverse_width <= 0:
        raise ValueError("Invalid index allocation or cell width")
    missing = []
    for point in points:
        cell = [math.floor((point[a] - origin[a]) * inverse_width) for a in range(3)]
        if all(0 <= cell[a] < dimensions[a] for a in range(3)):
            offset = 12 + 2 * (cell[0] + dimensions[0] * (cell[1] + dimensions[1] * cell[2]))
        else:
            offset = 8
        mask = words[offset] | (words[offset + 1] << 32)
        for index, light in enumerate(lights):
            supported = light["type"] == 1 or light["range_squared"] <= 0
            if not supported:
                distance_squared = sum((point[a] - light["position"][a]) ** 2 for a in range(3))
                supported = distance_squared <= light["range_squared"]
            if supported and not (mask & (1 << index)):
                if len(missing) < 20:
                    missing.append({"point": point, "light": index})
    return missing


def compare(capture, zero_indirect=False):
    report = json.loads((capture / "report.json").read_text())
    cases = {row["case"]: row for row in report["cases"]}
    expected = {"enumeration", "indexed", "missing_directional"}
    if not report.get("captured") or set(cases) != expected:
        raise ValueError("Incomplete transport cases")
    reference = cases["enumeration"]
    for row in cases.values():
        if row["frame"] != 192 or row["size"] != [320, 180] or row["stride"] != 112:
            raise ValueError("Transport shape/frame mismatch")
        if row["jitter"] != reference["jitter"]:
            raise ValueError("Jitter differs: transport comparison is not controlled")
        rr = row.get("reconstruction", {})
        if (rr.get("backend") != "DLSS" or not rr.get("viewport_renderer") or
                not rr.get("evaluation_succeeded") or rr.get("frames", 0) < 60 or
                rr.get("size") != [320, 180] or rr.get("output_size") != [640, 360]):
            raise ValueError("Missing native DLSS evaluation/dimension evidence")
    if reference["grid_enabled"] or not cases["indexed"]["grid_enabled"]:
        raise ValueError("Missing enumeration/indexed control")
    if not cases["missing_directional"]["negative_control"]:
        raise ValueError("Missing submitted negative control")
    light_bytes = (capture / "enumeration-light_bytes.bin").read_bytes()
    for name in expected:
        if (capture / (name + "-light_bytes.bin")).read_bytes() != light_bytes:
            raise ValueError("Submitted light order or parameters differ")
    lights = lights_from_bytes(light_bytes, reference["lights"])
    zero_count = sum(struct.unpack_from("<f", light_bytes, i * 112 + 48)[0] == 0 for i in range(reference["lights"]))
    if zero_indirect and zero_count != 32:
        raise ValueError("Expected 32 uploaded lights with zero indirect energy")
    grid = (capture / "indexed-grid_bytes.bin").read_bytes()
    rng = random.Random(117)
    points = [[rng.uniform(-20, 20), rng.uniform(-8, 12), rng.uniform(-20, 20)] for _ in range(12000)]
    for light in lights:
        if light["type"] == 1 or light["range_squared"] <= 0:
            continue
        points.append(list(light["position"]))
        radius = math.sqrt(light["range_squared"])
        for axis in range(3):
            for sign in (-1, 1):
                for padding in (-0.0001, 0, 0.0001):
                    point = list(light["position"])
                    point[axis] += sign * (radius + padding)
                    points.append(point)
    missing = oracle(grid, lights, points)
    if missing:
        raise ValueError("Submitted index omits supported lights: " + json.dumps(missing))
    negative_grid = (capture / "missing_directional-grid_bytes.bin").read_bytes()
    if not oracle(negative_grid, lights, points):
        raise ValueError("Oracle failed to detect the submitted omitted-light control")
    # A second negative control removes one finite light only from its own cell.
    local_negative = bytearray(grid)
    origin = struct.unpack_from("<3f", grid)
    inverse_width = struct.unpack_from("<f", grid, 12)[0]
    dimensions = struct.unpack_from("<3I", grid, 16)
    index = next(i for i, light in enumerate(lights) if light["type"] != 1 and light["range_squared"] > 0)
    point = lights[index]["position"]
    cell = [math.floor((point[a] - origin[a]) * inverse_width) for a in range(3)]
    offset = (12 + 2 * (cell[0] + dimensions[0] * (cell[1] + dimensions[1] * cell[2])) + index // 32) * 4
    value = struct.unpack_from("<I", local_negative, offset)[0] & ~(1 << (index % 32))
    struct.pack_into("<I", local_negative, offset, value)
    if not oracle(local_negative, lights, [point]):
        raise ValueError("Oracle failed to detect an omitted finite light in a local cell")
    colors = {name: (capture / (name + "-raw.bin")).read_bytes() for name in expected}
    if any(len(data) != 320 * 180 * 8 for data in colors.values()):
        raise ValueError("Raw HDR transport is incomplete")
    if colors["enumeration"] != colors["indexed"]:
        raise ValueError("Indexed raw transport differs from full enumeration")
    raw = list(struct.iter_unpack("<4e", colors["enumeration"]))
    if not all(math.isfinite(value) for pixel in raw for value in pixel):
        raise ValueError("Non-finite HDR transport")
    mean_rgb = sum(sum(pixel[:3]) for pixel in raw) / (len(raw) * 3)
    if mean_rgb <= 0.00001:
        raise ValueError("Black transport cannot qualify equivalence")
    negative = list(struct.iter_unpack("<4e", colors["missing_directional"]))
    changed_fraction = sum(a[:3] != b[:3] for a, b in zip(raw, negative)) / len(raw)
    if changed_fraction <= 0.01:
        raise ValueError("Submitted missing light did not measurably change raw GPU color")
    return {"transport_byte_identical": True, "native_rr_verified": True, "oracle_points": len(points),
            "submitted_negative_detected": True, "local_negative_detected": True,
            "mean_linear_rgb": mean_rgb, "negative_changed_pixel_fraction": changed_fraction,
            "capture_sha256": {p.name: digest(p) for p in sorted(capture.glob("*.bin"))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation-layers", type=Path, required=True)
    parser.add_argument("--render-thread", choices=("safe", "separate"), default="safe")
    parser.add_argument("--zero-indirect", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose fresh output; preserve earlier attempts")
    output = args.output.resolve()
    project = output / "project"
    project.mkdir(parents=True)
    source = Path(__file__).with_name("probe_rt_light_grid.gd")
    shutil.copyfile(source, project / "probe.gd")
    (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Light index transport fixture"\n[display]\nwindow/size/viewport_width=640\nwindow/size/viewport_height=360\n[rendering]\nrenderer/rendering_method="forward_plus"\nrendering_device/driver.windows="vulkan"\n')
    with (project / "project.godot").open("a") as stream:
        stream.write('streamline/project_id="' + str(uuid.uuid4()) + '"\n')
    engine = args.engine.resolve()
    real_engine = engine.with_name(engine.name.replace(".console.exe", ".exe"))
    runtime_manifest = Path(__file__).resolve().parents[2] / "drivers/streamline/runtime_manifest.json"
    runtime = json.loads(runtime_manifest.read_text())
    if runtime.get("runtime_flavor") != "production" or len(runtime.get("files", [])) != 12:
        raise ValueError("Missing production runtime manifest")
    runtime_files = [engine.parent / item["name"] for item in runtime["files"]]
    for path, item in zip(runtime_files, runtime["files"]):
        if digest(path) != item["sha256"]:
            raise ValueError("Runtime does not match the pinned production archive: " + path.name)
    renderer = Path(__file__).resolve().parents[2] / "servers/rendering/renderer_rd"
    source_inputs = [renderer / "forward_clustered/render_raytracing.cpp",
                     renderer / "forward_clustered/render_raytracing.h",
                     renderer / "shaders/raytracing/raytracing_lights_inc.glsl"]
    inputs = [real_engine, source, Path(__file__), project / "probe.gd", project / "project.godot", runtime_manifest, *source_inputs, *runtime_files]
    hashes = {str(p.resolve()): digest(p) for p in inputs}
    environment = os.environ.copy()
    environment.update(GODOT_RT_LIGHT_GRID_CAPTURE="1", GODOT_RT_LIGHT_GRID_DIAGNOSTICS="1",
                       GODOT_DLSS_DIAGNOSTICS="1", GODOT_RT_LIGHT_PROPOSALS="0",
                       VK_LAYER_PATH=str(args.validation_layers.resolve()),
                       VK_INSTANCE_LAYERS="VK_LAYER_KHRONOS_validation", VK_VALIDATION_VALIDATE_SYNC="true")
    command = [str(engine), "--path", str(project), "--render-thread", args.render_thread,
               "--gpu-validation", "--script", "res://probe.gd", "--", "--output=" + str(output / "capture")]
    if args.zero_indirect:
        command.append("--zero-indirect")
    result = {"passed": False, "validation": True, "render_thread": args.render_thread,
              "performance_acceptance": False, "zero_indirect": args.zero_indirect, "input_sha256": hashes}
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
            process = subprocess.run(command, env=environment, stdout=stdout, stderr=stderr, timeout=660, creationflags=flags)
        logs = (output / "stdout.log").read_text(errors="replace") + (output / "stderr.log").read_text(errors="replace")
        if process.returncode or re.search(r"^ERROR:|SCRIPT ERROR|VUID-|SYNC-HAZARD|leaked at exit", logs, re.M):
            raise ValueError("Renderer or synchronization validation failed; inspect logs")
        if any(digest(Path(p)) != value for p, value in hashes.items()):
            raise ValueError("Fixture inputs changed")
        if json.loads((output / "capture/report.json").read_text()).get("zero_indirect", False) != args.zero_indirect:
            raise ValueError("Zero-indirect fixture request differs from capture")
        result.update(compare(output / "capture", args.zero_indirect))
        result["passed"] = True
    except Exception as error:
        result["error"] = str(error)
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"input_sha256", "capture_sha256"}}))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
