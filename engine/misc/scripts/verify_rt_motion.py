"""Check captured primary RT motion against depth-reconstructed geometry.

The fixture has one translating, unrotated box above a stationary horizontal
floor. Camera projection data comes from the actual RT uniform buffer. This is
a geometric correctness check, not image-quality or performance acceptance.
"""
import argparse
import json
import math
from pathlib import Path
import statistics
import struct


def matrix(values):
    return [[values[column * 4 + row] for column in range(4)] for row in range(4)]


def multiply(m, v):
    return [sum(a * b for a, b in zip(row, v)) for row in m]


def inverse(m):
    rows = [list(row) + [float(i == j) for j in range(4)] for i, row in enumerate(m)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda r: abs(rows[r][column]))
        if abs(rows[pivot][column]) < 1e-20:
            raise ValueError("Singular captured projection")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        rows[column] = [value / scale for value in rows[column]]
        for row in range(4):
            if row == column:
                continue
            weight = rows[row][column]
            rows[row] = [a - weight * b for a, b in zip(rows[row], rows[column])]
    return [row[4:] for row in rows]


def uv(m, world):
    clip = multiply(m, [*world, 1.0])
    return [clip[i] / clip[3] * 0.5 + 0.5 for i in range(2)]


def verify(capture, step_x, box_center_x):
    width, height = map(int, (capture / "size.txt").read_text().split())
    velocity = (capture / "velocity.bin").read_bytes()
    depth = (capture / "rt_depth.bin").read_bytes()
    params = (capture / "raytracing_params.bin").read_bytes()
    if len(velocity) != width * height * 4 or len(depth) != width * height * 4 or len(params) != 192:
        raise ValueError("Unexpected captured guide dimensions")
    constants = struct.unpack("<48f", params)
    previous = matrix(constants[16:32])
    current = matrix(constants[32:48])
    inv_current = inverse(current)
    errors = {"stationary_floor": [], "moving_box": []}
    for y in range(1, height - 1, 2):
        for x in range(1, width - 1, 2):
            offset = (y * width + x) * 4
            z = struct.unpack_from("<f", depth, offset)[0]
            if z <= 0:
                continue
            position = multiply(inv_current, [(x + .5) / width * 2 - 1, (y + .5) / height * 2 - 1, z, 1.0])
            world = [v / position[3] for v in position[:3]]
            if abs(world[1]) < .001:
                # Box and floor meet at Y=0. At their contact edge a depth
                # sample can belong to either surface, so height alone is not
                # a reliable ID. Keep the rest of the floor as the static set.
                if abs(world[0] - box_center_x) < .52 and abs(world[2]) < .52:
                    continue
                group = "stationary_floor"
                old_world = world
            elif .05 < world[1] < 1.01:
                group = "moving_box"
                old_world = [world[0] - step_x, world[1], world[2]]
            else:
                continue
            current_uv = uv(current, world)
            previous_uv = uv(previous, old_world)
            expected = [a - b for a, b in zip(previous_uv, current_uv)]
            actual = struct.unpack_from("<2e", velocity, offset)
            error = math.hypot((actual[0] - expected[0]) * width, (actual[1] - expected[1]) * height)
            if not math.isfinite(error):
                raise ValueError("Non-finite reconstructed motion")
            errors[group].append(error)
    groups = {}
    for name, values in errors.items():
        if len(values) < 100:
            raise ValueError(f"Insufficient fixture coverage: {name}")
        values.sort()
        groups[name] = {"samples": len(values), "maximum_error_pixels": values[-1],
                        "median_error_pixels": statistics.median(values),
                        "p99_error_pixels": values[min(len(values) - 1, int(len(values) * .99))],
                        "passed": values[-1] < .05}
    return {"passed": all(row["passed"] for row in groups.values()), "size": [width, height],
            "rt_frame_index": constants[15], "object_step_x": step_x, "box_center_x": box_center_x,
            "contact_footprint_margin_m": .02, "groups": groups,
            "tolerance_pixels": .05, "quality_accepted": False, "performance_accepted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--step-x", type=float, default=.01)
    parser.add_argument("--box-center-x", type=float, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.capture, args.step_x, args.box_center_x)
    output = args.output or args.capture / "motion-analysis.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 7)


if __name__ == "__main__":
    main()
