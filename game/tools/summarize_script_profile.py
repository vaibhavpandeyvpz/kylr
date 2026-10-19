"""Summarize Godot's diagnostic debugger capture, discarding partial frames."""
import json
import argparse
from collections import defaultdict
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("path", nargs="?", default="reports/script-profile.json")
parser.add_argument("--capture", type=int, help="One-based capture number; default: latest")
args = parser.parse_args()
data = json.loads(Path(args.path).read_text())
captures = data.get("captures", []) + [data]
capture_number = len(captures) if args.capture is None else args.capture
if not 1 <= capture_number <= len(captures):
    parser.error(f"capture must be between 1 and {len(captures)}")
data = captures[capture_number - 1]
print(f"Capture {capture_number}/{len(captures)} (function IDs are local to each capture)")
frames = data["frames"][2:]
functions = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
servers = defaultdict(float)
for frame in frames:
    cursor = 7
    for _ in range(frame[6]):
        name, size = frame[cursor:cursor + 2]
        cursor += 2
        for offset in range(cursor, cursor + size, 2):
            servers[name + "/" + frame[offset]] += frame[offset + 1]
        cursor += size
    size = frame[cursor]
    cursor += 1
    assert cursor + size == len(frame)
    for offset in range(cursor, cursor + size, 5):
        signature, *cost = frame[offset:offset + 5]
        for index, value in enumerate(cost):
            functions[data["signatures"][str(signature)]][index] += value
count = max(1, len(frames))
print(f"Diagnostic debug capture: {len(frames)} complete frames; not release FPS")
for index, label in [(1, "frame"), (2, "process"), (3, "physics"), (5, "script")]:
    print(f"{label}: {sum(frame[index] for frame in frames) * 1000 / count:.3f} ms/frame")
print("\nTop self cost: calls/frame self_ms/frame total_ms/frame function")
for name, (calls, own, total, internal) in sorted(functions.items(), key=lambda item: item[1][1], reverse=True)[:30]:
    print(f"{calls / count:8.1f} {own * 1000 / count:8.3f} {total * 1000 / count:8.3f} {name}")
print("\nNative server timings (may overlap):")
for name, cost in sorted(servers.items(), key=lambda item: item[1], reverse=True)[:12]:
    print(f"{cost * 1000 / count:8.3f} {name}")
