"""Collect per-binary evidence without treating old or failed runs as acceptance."""
import hashlib
import json
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
report_path = root / "reports/nvidia-rt-investigation.json"
report = json.loads(report_path.read_text(encoding="utf-8"))
binary = root.parent / "engine/bin/godot.windows.editor.x86_64.exe"
report["engine_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest().upper()
report["production_release"] = False
report["tests"] = {}
for path in sorted((root / "reports").glob("*acceptance*.process.json")):
    entry = json.loads(path.read_text(encoding="utf-8-sig"))
    metrics_path = path.with_name("nvidia-" + path.name.replace(".process.json", ".json"))
    if metrics_path.exists():
        entry["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8-sig"))
    entry["matches_current_binary"] = entry.get("binary_sha256") == report["engine_sha256"]
    entry["run_passed"] = entry.get("exit_code") == 0 and not entry.get("timed_out") and not entry.get("diagnostics_failed")
    capture = metrics_path.with_suffix(".png")
    if capture.exists():
        with Image.open(capture) as image:
            entry["captured_size"] = list(image.size)
            entry["output_dimensions_verified"] = image.size == (1920, 1080)
        entry["run_passed"] &= entry["output_dimensions_verified"]
    report["tests"][entry["name"]] = entry
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"current_binary": report["engine_sha256"], "runs": len(report["tests"]), "production_release": False}))
