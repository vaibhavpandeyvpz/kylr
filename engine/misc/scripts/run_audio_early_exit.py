"""Check abrupt headless PCM teardown, including already queued stop requests.

This tests resource lifetime, not audible output or playback performance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Use a fresh output directory; preserve previous evidence")
    project = output / "project"
    project.mkdir(parents=True)
    (project / "project.godot").write_text("config_version=5\n", encoding="utf8")
    source = Path(__file__).with_name("probe_audio_early_exit.gd")
    shutil.copyfile(source, project / "probe.gd")
    engine = args.engine.resolve()
    binary = engine.with_name(engine.name.replace(".console.exe", ".exe"))
    frozen = {str(path): digest(path) for path in [engine, binary, source, Path(__file__)]}
    cases = []
    for stopped in [False, True]:
        command = [str(engine), "--headless", "--verbose", "--path", str(project), "--script", "res://probe.gd", "--"]
        if stopped:
            command.append("--stop-first")
        log_path = output / ("stopping.log" if stopped else "active.log")
        with log_path.open("w", encoding="utf8") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=60)
        log = log_path.read_text(encoding="utf8", errors="replace")
        clean = not re.search(r"ERROR:|SCRIPT ERROR:|ObjectDB.*leaked at exit|Leaked instance:|Resource[s]? still in use", log)
        marker = "AUDIO_EARLY_EXIT_READY players=16 stopped=" + str(stopped).lower()
        cases.append({"stopped_before_quit": stopped, "exit_code": result.returncode,
                      "passed": result.returncode == 0 and clean and marker in log, "clean_log": clean,
                      "ready_marker": marker in log, "command": command})
    unchanged = all(digest(Path(path)) == value for path, value in frozen.items())
    passed = unchanged and all(case["passed"] for case in cases)
    report = {"passed": passed, "cases": cases, "inputs": frozen, "unchanged": unchanged,
              "audible_output_accepted": False, "performance_accepted": False}
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"passed": passed, "cases": cases}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
