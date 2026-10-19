"""Summarize Godot visual-profiler timestamps; diagnostic timings are not release FPS."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("path", type=Path)
parser.add_argument("--sort", choices=["cpu", "gpu"], default="gpu")
parser.add_argument("--limit", type=int, default=30)
args = parser.parse_args()
if args.limit < 1:
    parser.error("--limit must be positive")
data = json.loads(args.path.read_text())
frames = {frame[0]: frame for frame in data["visual_frames"]}
frames = list(frames.values())[2:]
costs = defaultdict(lambda: [0.0, 0.0])
totals = []
for frame in frames:
    assert len(frame) == 2 + frame[1] and frame[1] % 3 == 0
    areas = [frame[i:i + 3] for i in range(2, len(frame), 3)]
    totals.append(areas[-1][2] - areas[0][2])
    stack = []
    for current, following in zip(areas, areas[1:]):
        name, cpu, gpu = current
        if name.startswith(">"):
            stack.append(name[1:].strip())
            name = "Scope setup"
        elif name.startswith("<"):
            assert stack
            stack.pop()
            name = "Scope finish"
        elif name.startswith(("vp_begin_", "vp_end_")):
            name = name.rsplit("_", 1)[0]
        path = "/".join(stack + [name])
        costs[path][0] += following[1] - cpu
        costs[path][1] += following[2] - gpu
count = max(1, len(frames))
print(f"Diagnostic rendering capture: {len(frames)} unique complete frames; not release FPS")
print(f"Mean GPU timestamp span: {mean(totals):.3f} ms")
print("Exclusive intervals, mean CPU ms / GPU ms per frame:")
sort_index = 0 if args.sort == "cpu" else 1
for name, (cpu, gpu) in sorted(costs.items(), key=lambda item: -item[1][sort_index])[:args.limit]:
    print(f"{cpu/count:7.3f} {gpu/count:7.3f} {name}")
errors = data.get("errors", [])
print(f"Runtime errors: {sum(not entry[9] for entry in errors)}; warnings: {sum(bool(entry[9]) for entry in errors)}")
