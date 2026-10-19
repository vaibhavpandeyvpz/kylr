"""Stress concurrent audio routing with silent PCM; this is not an FPS test."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--driver", default="Dummy")
    parser.add_argument("--seconds", type=int, choices=range(5, 61), default=20)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Use a fresh output directory; preserve previous evidence")
    project = output / "project"
    project.mkdir(parents=True)
    (project / "project.godot").write_text("config_version=5\n", encoding="utf8")
    requested_engine = args.engine.resolve()
    engine = requested_engine.with_name(requested_engine.name.replace(".console.exe", ".exe"))
    source = Path(__file__).with_name("probe_audio_bus_routes.gd").resolve()
    paths = [requested_engine, engine, source, Path(__file__).resolve()]
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    # Suppress an interactive crash dialog for this process and its child only.
    if hasattr(ctypes, "windll"):
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    command = [str(engine), "--headless", "--disable-crash-handler", "--audio-driver", args.driver,
               "--path", str(project), "--script", str(source), "--",
               "--seconds=" + str(args.seconds), "--output=" + str(output / "report.json")]
    timed_out = False
    with (output / "runtime.log").open("w", encoding="utf8") as stream:
        child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            code = child.wait(timeout=args.seconds + 20)
        except subprocess.TimeoutExpired:
            timed_out = True
            child.kill()
            code = child.wait()
    log = (output / "runtime.log").read_text(encoding="utf8", errors="replace")
    clean = not re.search(r"ERROR:|SCRIPT ERROR|instances were leaked|Leaked instance:", log)
    report = json.loads((output / "report.json").read_text()) if (output / "report.json").exists() else {}
    unchanged = all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == value for path, value in hashes.items())
    passed = code == 0 and not timed_out and clean and unchanged and report.get("passed") is True
    result = {"passed": passed, "exit_code": code, "timed_out": timed_out, "driver": args.driver,
              "clean_log": clean, "unchanged": unchanged, "inputs": hashes, "command": command,
              "probe": report, "performance_acceptance": False, "audible_quality_acceptance": False}
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
