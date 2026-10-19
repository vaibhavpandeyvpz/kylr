"""Compare deterministic HDR captures; never treats them as FPS acceptance."""

import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys


def load(directory):
    rows = json.loads((directory / "captures.json").read_text(encoding="utf-8"))["captures"]
    expected = {"diffuse", "metal", "clearcoat", "transmission", "rim_backlight",
                "custom_area", "transparent", "lights_disabled_control"}
    if len(rows) != len(expected) or {row["name"] for row in rows} != expected:
        raise ValueError("Incomplete or duplicated material cases")
    result = {}
    for row in rows:
        raw = (directory / (row["name"] + ".rgba32f")).read_bytes()
        if len(raw) != row["bytes"] or len(raw) != row["width"] * row["height"] * 16:
            raise ValueError("Incorrect HDR payload length")
        values = array.array("f")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Non-finite HDR output")
        result[row["name"]] = (row, values, hashlib.sha256(raw).hexdigest())
    # Identical material/geometry: only the three area lights are disabled.
    lit = result["transparent"][1]
    dark = result["lights_disabled_control"][1]
    changed = sum(max(abs(lit[i + channel] - dark[i + channel]) for channel in range(3)) > .005
                  for i in range(0, len(lit), 4))
    if changed < 100:
        raise ValueError("Negative control did not establish visible area-light contributions")
    return result, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh output path; preserve previous evidence")
    reference, reference_control = load(args.reference)
    candidate, candidate_control = load(args.candidate)
    rows = []
    for name, (metadata, before, before_hash) in reference.items():
        after_metadata, after, after_hash = candidate[name]
        if metadata != after_metadata:
            raise ValueError("Capture configurations differ")
        maximum = max(abs(a - b) for a, b in zip(before, after))
        rows.append({"case": name, "max_abs_error": maximum,
                     "changed_channels": sum(a != b for a, b in zip(before, after)),
                     "byte_exact": before_hash == after_hash,
                     "reference_sha256": before_hash, "candidate_sha256": after_hash,
                     "passed": maximum <= .0005})
    result = {"passed": all(row["passed"] for row in rows), "max_abs_tolerance": .0005,
              "negative_control_pixels": [reference_control, candidate_control],
              "cases": rows, "performance_acceptance": False}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
