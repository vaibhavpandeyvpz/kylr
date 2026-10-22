"""Summarize native --gpu-profile logs bounded by the combat sample markers.

Native printed records are interval summaries, not individual frame timings.
Absent stages are not treated as zero, and nested scopes are never added together.
"""
import argparse
import json
import re
import statistics
from pathlib import Path


def summarize_alpha(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    begin = [i for i, line in enumerate(lines) if line.startswith("PROFILE_SAMPLE_BEGIN ")]
    end = [i for i, line in enumerate(lines) if line.startswith("PROFILE_SAMPLE_END ")]
    if len(begin) != 1 or len(end) != 1 or begin[0] >= end[0]:
        raise ValueError("Expected one complete sample window")
    scene = json.loads(path.with_name(path.name.replace(".stdout.log", ".json")).read_text())
    phases = scene.get("alpha_isolation", {}).get("phases", [])
    if len(phases) != 7 or not scene["alpha_isolation"].get("restored"):
        raise ValueError("Incomplete restored alpha-isolation phases")
    records = [[] for _ in phases]
    filters = [[] for _ in phases]
    seen = []
    phase = -1
    current = None
    for line in lines[begin[0]+1:end[0]]:
        marker = re.match(r"PROFILE_ALPHA_PHASE index=(\d+) ", line)
        if marker:
            phase = int(marker[1])
            seen.append(phase)
            current = None
            continue
        if not 0 <= phase < len(phases):
            continue
        total = re.fullmatch(r"GPU PROFILE \(total ([\d.]+)ms\):\s*", line)
        if total:
            current = {"total_ms": float(total[1]), "stages_ms": {}}
            records[phase].append(current)
            continue
        stage = re.fullmatch(r"\s+-([^\n:]+): ([\d.]+)ms\s*", line)
        if stage and current is not None:
            if stage[1] in current["stages_ms"]:
                raise ValueError("Duplicate stage in native interval")
            current["stages_ms"][stage[1]] = float(stage[2])
        native_filter = re.fullmatch(r"GPU_ALPHA_FILTER mask=(.*?) skipped_elements=(\d+)", line)
        if native_filter:
            filters[phase].append((native_filter[1], int(native_filter[2])))
    if seen != list(range(7)):
        raise ValueError("Phase markers are incomplete or out of order")
    summaries = []
    for index, row in enumerate(phases):
        # Native output averages the preceding interval. Drop boundary intervals
        # on both sides, and possible render-thread boundary acknowledgements.
        interior = records[index][1:-1]
        native = filters[index][2:-2]
        if len(interior) < 3 or not native or any(mask != row["mask"] for mask, _ in native):
            raise ValueError("Insufficient controlled native intervals: " + row["label"])
        stages = {}
        for name in ("Render 3D Opaque Pass", "Render 3D Transparent Pass"):
            values = [r["stages_ms"][name] for r in interior if name in r["stages_ms"]]
            if len(values) < 3:
                raise ValueError("Missing stage coverage: " + name)
            stages[name] = {"intervals":len(values), "median_ms":statistics.median(values),
                            "min_ms":min(values), "max_ms":max(values)}
        skipped = [count for _, count in native]
        if not row["mask"] and any(skipped):
            raise ValueError("Restored baseline still omits draws")
        summaries.append({"label":row["label"], "mask":row["mask"], "gpu_stages":stages,
                          "native_filter_frames":len(native), "max_skipped_elements":max(skipped),
                          "filter_effective":bool(max(skipped))})
    comparisons = []
    for index in (1, 3, 5):
        before, without, after = [summaries[i]["gpu_stages"]["Render 3D Transparent Pass"]["median_ms"]
                                  for i in (index-1, index, index+1)]
        comparisons.append({"group":phases[index]["label"], "baseline_before_ms":before,
                            "without_ms":without, "baseline_after_ms":after,
                            "saving_vs_neighbor_mean_ms":(before+after)/2-without,
                            "filter_effective":summaries[index]["filter_effective"]})
    return {"source":str(path.resolve()), "performance_acceptance":False,
            "method":"native interval summaries; boundary records discarded; live simulation, not deterministic replay",
            "phases":summaries, "comparisons":comparisons}


def summarize(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    begins = [i for i, line in enumerate(lines) if line.startswith("PROFILE_SAMPLE_BEGIN ")]
    ends = [i for i, line in enumerate(lines) if line.startswith("PROFILE_SAMPLE_END ")]
    if len(begins) != 1 or len(ends) != 1 or ends[0] <= begins[0]:
        raise ValueError("Expected exactly one ordered pair of sample markers")
    records = []
    current = None
    for line in lines[begins[0] + 1:ends[0]]:
        total = re.fullmatch(r"GPU PROFILE \(total ([\d.]+)ms\):\s*", line)
        if total:
            current = {"total_ms": float(total[1]), "stages_ms": {}}
            records.append(current)
            continue
        stage = re.fullmatch(r"\s+-([^\n:]+): ([\d.]+)ms\s*", line)
        if stage and current is not None:
            if stage[1] in current["stages_ms"]:
                raise ValueError("Duplicate stage in a native profile record: " + stage[1])
            current["stages_ms"][stage[1]] = float(stage[2])
    if len(records) < 3:
        raise ValueError("Too few native profile records in the measured window")
    # The first printed interval can include work before the begin marker.
    records = records[1:]
    names = sorted({name for record in records for name in record["stages_ms"]})

    def stats(values):
        return {"records": len(values), "mean_ms": statistics.mean(values),
                "median_ms": statistics.median(values), "min_ms": min(values),
                "max_ms": max(values)}

    return {"source": str(path.resolve()), "performance_acceptance": False,
            "record_type": "native interval summaries; not individual frames",
            "first_interval_discarded": True, "records": len(records),
            "total": stats([record["total_ms"] for record in records]),
            "stages": {name: stats([r["stages_ms"][name] for r in records
                                     if name in r["stages_ms"]]) for name in names}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--alpha-phases", action="store_true")
    args = parser.parse_args()
    report = summarize_alpha(args.log) if args.alpha_phases else summarize(args.log)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.alpha_phases:
        print(json.dumps(report["comparisons"], indent=2))
    else:
        print("Measured-window GPU diagnostics (not acceptance FPS):", report["records"], "intervals")
        for name, values in sorted(report["stages"].items(), key=lambda item: -item[1]["median_ms"])[:15]:
            print(f"{values['median_ms']:8.3f} ms median ({values['records']} intervals) {name}")
