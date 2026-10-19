"""Compare fixed-view captures. Metrics are diagnostics, never release/FPS gates."""
import argparse
import json
import math
from pathlib import Path
from statistics import mean

from PIL import Image, ImageChops, ImageDraw, ImageStat


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_images(directory, case):
    images = []
    for name in case["files"]:
        if Path(name).name != name:
            raise ValueError("Capture file must belong to its report directory")
        images.append(Image.open(directory / name).convert("RGB"))
    if not images or len({image.size for image in images}) != 1:
        raise ValueError("Missing captures or inconsistent dimensions")
    return images


def average(images):
    count = len(images)
    pixels = bytes(round(sum(values) / count) for values in zip(*(image.tobytes() for image in images)))
    return Image.frombytes("RGB", images[0].size, pixels)


def rms(image):
    return math.sqrt(mean(value * value for value in ImageStat.Stat(image).rms)) / 255.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    reference = read_json(args.reference / "report.json")
    candidate = read_json(args.candidate / "report.json")
    reference_manifest = read_json(args.reference / "manifest.json")
    candidate_manifest = read_json(args.candidate / "manifest.json")
    if reference.get("camera_motion") or candidate.get("camera_motion"):
        raise ValueError("Moving-camera captures cannot use fixed-view mean-image comparisons")
    if reference["mode"] != "reference" or not reference["complete"] or not candidate["complete"]:
        raise ValueError("Complete raw reference and candidate captures are required")
    for key in ("map", "output", "frozen_simulation"):
        if reference[key] != candidate[key]:
            raise ValueError("Capture configuration mismatch: " + key)
    if not reference["frozen_simulation"] or reference_manifest["probe_sha256"] != candidate_manifest["probe_sha256"]:
        raise ValueError("A common fixed-view probe revision is required")
    if not reference_manifest.get("capture_passed") or not candidate_manifest.get("capture_passed") or not reference_manifest.get("validation") or not candidate_manifest.get("validation"):
        raise ValueError("Both captures must pass Vulkan validation")
    if not reference_manifest.get("engine_sha256") or reference_manifest["engine_sha256"] != candidate_manifest.get("engine_sha256"):
        raise ValueError("Engine binaries differ")
    if reference.get("capture_revision", 1) != candidate.get("capture_revision", 1):
        raise ValueError("Arena capture revisions differ")
    if reference.get("capture_revision", 1) < 5:
        raise ValueError("Raw references require revision 5 reconstruction bypass controls")
    renderer = reference["renderer"]
    if (renderer["denoiser"] != 0 or renderer["scaling_mode"] != 0
            or renderer["internal_scale"] != 1.0 or renderer["taa"]
            or renderer["msaa"] != 0 or renderer["screen_space_aa"] != 0):
        raise ValueError("Raw reference uses reconstruction or antialiasing")
    for report, manifest in ((reference, reference_manifest), (candidate, candidate_manifest)):
        for key in ("capture_revision", "rr_preset_requested", "reference_batch_spp"):
            if report[key] != manifest[key]:
                raise ValueError("Capture manifest differs: " + key)
    for key in ("rr_preset_requested", "reference_batch_spp", "reference_spp"):
        if reference[key] != candidate[key]:
            raise ValueError("Requested capture settings differ: " + key)
    for capture in reference["reference_captures"]:
        budget = reference["reference_spp"]
        if (not capture["linear_hdr"] or capture["completed_weight"] != budget
                or capture["samples_per_internal_pixel"] != budget
                or sum(capture["batches"]) != budget
                or any(not 0 < batch <= reference["reference_batch_spp"] for batch in capture["batches"])):
            raise ValueError("Raw reference has an incomplete HDR sample budget")
    if reference.get("capture_revision", 1) >= 2:
        helper_hash = reference_manifest.get("reference_helper_sha256")
        if not helper_hash or helper_hash != candidate_manifest.get("reference_helper_sha256"):
            raise ValueError("Arena HDR reference helper provenance differs")
    if reference_manifest["runtime_dlls"] != candidate_manifest["runtime_dlls"]:
        raise ValueError("Runtime libraries differ")
    if reference_manifest.get("inputs") != candidate_manifest.get("inputs"):
        raise ValueError("Frozen arena sources, assets or import caches differ")
    cases = {case["name"]: case for case in reference["cases"]}
    if cases.keys() != {case["name"] for case in candidate["cases"]}:
        raise ValueError("Capture views differ")
    width, height = reference["output"]
    sheet = Image.new("RGB", (width * 3, (height + 24) * len(cases)), "#131b22")
    draw = ImageDraw.Draw(sheet)
    results = []
    # Fixed camera-specific patches isolate visible flat-finish mottling. Full
    # frames and reflective racks are retained so these do not hide hard cases.
    patches = {
        "laboratory": {"wall": (140, 165, 260, 240), "ceiling": (170, 10, 430, 85), "racks": (490, 130, 635, 275)},
        "habitat": {"wall": (240, 100, 385, 255)},
        "lower-deck": {"ceiling": (200, 10, 450, 70), "floor": (200, 300, 450, 350)},
    }
    # Camera-relative rectangles are authored at 640x360. Preserve their scene
    # coverage when inspecting the actual 1080p output; these remain diagnostics.
    patches = {name: {label: tuple(round(value * (width / 640 if i % 2 == 0 else height / 360))
                                   for i, value in enumerate(rect))
                      for label, rect in areas.items()} for name, areas in patches.items()}
    for row, case in enumerate(candidate["cases"]):
        baseline = cases[case["name"]]
        for key in ("position", "target"):
            if baseline[key] != case[key]:
                raise ValueError("Camera mismatch: " + case["name"])
        raw = load_images(args.reference, baseline)
        filtered = load_images(args.candidate, case)
        if raw[0].size != filtered[0].size or raw[0].size != (width, height):
            raise ValueError("Capture dimensions differ from reports")
        raw_mean, filtered_mean = average(raw), average(filtered)
        split_difference = ImageChops.difference(average(raw[::2]), average(raw[1::2]))
        difference = ImageChops.difference(raw_mean, filtered_mean)
        entry = {
            "case": case["name"],
            "reference_frames": len(raw), "candidate_frames": len(filtered),
            "mean_image_rgb_rmse_sdr": rms(difference),
            "mean_single_frame_rgb_rmse_sdr": mean(rms(ImageChops.difference(raw_mean, image)) for image in filtered),
            "temporal_residual_rms_sdr": mean(rms(ImageChops.difference(filtered_mean, image)) for image in filtered),
            "reference_independent_split_half_rgb_rmse_sdr": rms(split_difference),
            "settling": [],
            "patches": {},
        }
        for label, rect in patches.get(case["name"], {}).items():
            entry["patches"][label] = {
                "rect": rect,
                "mean_image_rgb_rmse_sdr": rms(difference.crop(rect)),
                "temporal_residual_rms_sdr": mean(rms(ImageChops.difference(filtered_mean, image).crop(rect)) for image in filtered),
                "reference_independent_split_half_rgb_rmse_sdr": rms(split_difference.crop(rect)),
            }
        for sample in case.get("settling", []):
            image = Image.open(args.candidate / sample["file"]).convert("RGB")
            if image.size != (width, height):
                raise ValueError("Incorrect settling image dimensions")
            residual = ImageChops.difference(raw_mean, image)
            adapter = sample["denoiser"]["adapter"]
            entry["settling"].append({
                "render_frames_after_ready": sample["render_frames_after_ready"],
                "history_age": adapter["history_age"], "denoiser_frames": adapter["frames"],
                "rgb_rmse_sdr": rms(residual),
                "patches": {label: rms(residual.crop(rect))
                            for label, rect in patches.get(case["name"], {}).items()},
            })
        results.append(entry)
        for column, (label, image) in enumerate((
            ("Raw reference mean", raw_mean),
            (candidate["mode"] + " mean", filtered_mean),
            ("Absolute difference x4", difference.point(lambda value: min(255, value * 4))),
        )):
            offset = row * (height + 24)
            sheet.paste(image, (column * width, offset + 24))
            draw.text((column * width + 8, offset + 5), case["name"] + " / " + label, fill="white")
    args.output.mkdir(parents=True, exist_ok=False)
    sheet.save(args.output / "sheet.png")
    report = {
        "map": candidate["map"], "mode": candidate["mode"], "output": candidate["output"],
        "reference": str(args.reference), "candidate": str(args.candidate),
        "matching_engine": reference_manifest["engine_sha256"] == candidate_manifest["engine_sha256"],
        "reference_engine_sha256": reference_manifest["engine_sha256"],
        "candidate_engine_sha256": candidate_manifest["engine_sha256"],
        "reference_simulation_fps": reference_manifest.get("simulation_fps"),
        "candidate_simulation_fps": candidate_manifest.get("simulation_fps"),
        "cases": results, "quality_accepted": False, "performance_acceptance": False,
        "note": "Static LDR diagnostics with matching engine/probe/DLL provenance. Inspect images and moving full-resolution scenes separately.",
    }
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
