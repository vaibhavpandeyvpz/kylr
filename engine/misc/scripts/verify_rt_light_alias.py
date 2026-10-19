#!/usr/bin/env python3
"""Independent distribution and RIS-energy checks against the compiled renderer helper.

This is numerical evidence only, not GPU transport, image-quality or FPS approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    root = Path(__file__).resolve().parents[2]
    paths = [args.probe.resolve(strict=True), Path(__file__).resolve(),
             root / "misc/scripts/probe_rt_light_alias.cpp",
             root / "servers/rendering/renderer_rd/forward_clustered/rt_light_sampling.h"]
    frozen = {str(path): digest(path) for path in paths}
    process = subprocess.run([str(paths[0])], capture_output=True, text=True, check=True)
    cases = [json.loads(line) for line in process.stdout.splitlines() if line]
    expected_valid = {"one-zero", "all-zero", "uniform", "dominant", "mixed-zero", "wide", "large", "subnormal", "unequal-17"}
    expected_invalid = {"count-zero", "count-large", "negative", "infinite", "nan", "null-input"}
    if {case["name"] for case in cases} != expected_valid | expected_invalid or len(cases) != 15:
        raise ValueError("Fixture case coverage differs")
    rng = np.random.default_rng(593)
    rows = []
    negative_rejected = False
    for case in cases:
        name = case["name"]
        if name in expected_invalid:
            if case["accepted"] or not case["output_untouched"]:
                raise ValueError("Invalid input modified the output: " + name)
            rows.append({"name": name, "rejected_without_writes": True})
            continue
        n = case["count"]
        weights = np.asarray(case["weights"], dtype=np.float64)
        entries = np.asarray(case["entries"], dtype=np.float64)
        if not case["accepted"] or entries.shape != (n, 3) or not np.isfinite(entries).all():
            raise ValueError("Invalid table output: " + name)
        pdf, threshold, aliases = entries[:, 0], entries[:, 1], entries[:, 2].astype(np.int64)
        if (aliases < 0).any() or (aliases >= n).any() or (threshold < 0).any() or (threshold > 1).any() or (pdf <= 0).any():
            raise ValueError("Alias bounds/full support failure: " + name)
        # Integrate every stored bucket exactly; this oracle does not construct
        # an alias table or repeat its small/large-list algorithm.
        realized = threshold / n
        np.add.at(realized, aliases, (1 - threshold) / n)
        normalized = weights / weights.max() if weights.max() > 0 else np.zeros(n)
        desired = .9 * normalized / normalized.sum() + .1 / n if normalized.sum() > 0 else np.full(n, 1 / n)
        table_error = float(np.max(np.abs(realized - desired)))
        pdf_error = float(np.max(np.abs(realized - pdf)))
        if table_error > 4e-8 or pdf_error > 4e-8 or abs(realized.sum() - 1) > 1e-12 or (realized < .099999 / n).any():
            raise ValueError("Stored distribution/PDF differs: " + name)
        # 40,000 independent reservoirs, each with up to 16 proposals. This uses
        # inverse CDF selection, independent of the shader's streaming reservoir.
        trials, k = 40000, min(16, n)
        columns = rng.integers(n, size=(trials, k))
        samples = np.where(rng.random((trials, k)) < threshold[columns], columns, aliases[columns])
        index = np.arange(n, dtype=np.float64)
        rgb = np.stack((.2 + (index % 7) / 7, .1 + (index % 11) / 11, .3 + (index % 5) / 5), axis=1)
        rgb[index.astype(int) % 5 == 2] = 0  # Occluded lights remain part of M.
        target = rgb @ np.array([.2126, .7152, .0722]) + .01
        sample_weights = target[samples] / pdf[samples]
        sums = sample_weights.sum(axis=1)
        draw = rng.random(trials) * sums
        selected = np.minimum((np.cumsum(sample_weights, axis=1) < draw[:, None]).sum(axis=1), k - 1)
        chosen = samples[np.arange(trials), selected]
        estimate = rgb[chosen] * (sums / (k * target[chosen]))[:, None]
        exact = rgb.sum(axis=0)
        error = np.abs(estimate.mean(axis=0) - exact)
        standard_error = estimate.std(axis=0, ddof=1) / np.sqrt(trials)
        # Five measured standard errors plus arithmetic tolerance, not a
        # widened game-image threshold. All randomness is fixed and recorded.
        limit = 5 * standard_error + 1e-5 * np.maximum(exact, 1)
        if (error > limit).any():
            raise ValueError("RIS energy normalization failure: " + name)
        if name == "dominant":
            # Deliberately wrong selected-target/source-PDF normalization.
            bad = estimate * pdf[chosen, None]
            negative_error = np.abs(bad.mean(axis=0) - exact)
            negative_rejected = bool((negative_error > limit).all())
            if not negative_rejected:
                raise ValueError("Missing-PDF negative control was not rejected")
        rows.append({"name": name, "table_error": table_error, "pdf_error": pdf_error,
                     "energy_error": error.tolist(), "five_sigma_limit": limit.tolist(),
                     "samples": trials * k})
    if not negative_rejected or frozen != {str(path): digest(path) for path in paths}:
        raise ValueError("Negative control/input stability failure")
    return {"passed": True, "inputs": frozen, "seed": 593, "cases": rows,
            "wrong_pdf_negative_rejected": True, "gpu_transport_accepted": False,
            "image_quality_accepted": False, "performance_accepted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Preserve previous oracle receipts")
    try:
        result = run(args)
    except Exception as error:
        result = {"passed": False, "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "inputs"}))
    raise SystemExit(0 if result["passed"] else 1)
