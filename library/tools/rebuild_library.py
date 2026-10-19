"""Rebuild authored models, collision companions and available round-trip checks.

Run with .venv/Scripts/python.exe from library/. Jobs are serial;
the resumable report records source hashes, exact commands and fresh outputs.
This does not copy assets into a game or delete source files.
"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get('BLENDER_EXECUTABLE') or shutil.which('blender') or 'blender'
RANK = {"characters":0,"weapons":1,"gameplay":2,"environments":3,"architecture":4,"maps":6}
GENERATED = {".blend", ".glb", ".fbx", ".png", ".mp4", ".json"}


def save(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    temporary.replace(path)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_snapshot():
    # Include shared helpers, configuration and texture inputs, not just the
    # directly executed script. Ignored build outputs are recorded separately.
    paths = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "library"], cwd=ROOT.parent
    ).decode("utf8").split("\0")
    entries = {name.removeprefix('library/'): file_hash(ROOT.parent / name) if (ROOT.parent / name).is_file() else None
               for name in sorted(set(paths) - {""})}
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf8")).hexdigest()
    return digest, entries


def generated_inputs(folder):
    # Other native assets can supply imported geometry, sockets and dimensions.
    # Exclude this asset's own outputs when deciding whether resume is valid.
    return {p.relative_to(ROOT).as_posix(): file_hash(p)
            for p in sorted((ROOT / "models").rglob("*"))
            if p.is_file() and folder not in p.parents and
            (p.suffix in {".blend", ".glb", ".fbx"} or p.name.endswith("_rig.json"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--previews", action="store_true", help="Regenerate native preview images after validation")
    parser.add_argument("--showcases", action="store_true", help="Regenerate native animation showcases after validation")
    parser.add_argument("--report", type=Path, default=ROOT / "target/regeneration/clean-rebuild")
    parser.add_argument("--blender", default=BLENDER, help="Blender 5.2 executable; otherwise use BLENDER_EXECUTABLE or PATH")
    args = parser.parse_args()
    executable = shutil.which(args.blender)
    if executable is None:
        parser.error('Blender 5.2 is required: add it to PATH, set BLENDER_EXECUTABLE or pass --blender.')
    blender = Path(executable)
    target = args.report.resolve()
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / "report.json"
    report = json.loads(report_path.read_text()) if args.resume and report_path.exists() else {"jobs":{},"completed":False}
    report["completed"] = False
    models = list((ROOT / "models").rglob("model.py"))
    models.sort(key=lambda p:(5 if p.parent.name == "bridge" else RANK.get(p.relative_to(ROOT / "models").parts[0], 9), p.as_posix()))
    if args.only:
        missing = set(args.only) - {p.parent.name for p in models}
        if missing:
            parser.error("Unknown assets: " + ", ".join(sorted(missing)))
        models = [p for p in models if p.parent.name in args.only]
    report["assets"] = [p.parent.relative_to(ROOT).as_posix() for p in models]
    report["controller_pid"] = os.getpid()
    report["blender_sha256"] = file_hash(blender)
    for model in models:
        folder = model.parent
        jobs = [(folder / name, []) for name in ('architecture_variants.py', 'platform_variants.py')
                if (folder / name).exists()]
        jobs.append((model, []))
        if (folder / "collision.py").exists():
            collision = folder / "collision.py"
            # Shared collider generators render comparison views by default.
            # Keep a source rebuild free of hidden GPU jobs unless requested.
            options = ["--no-render"] if not args.previews and "--no-render" in collision.read_text(encoding="utf8") else []
            jobs.append((collision, options))
        if folder.name == "tensor":
            jobs.extend([(model, ["--shield-only"]), (model, ["--shield-roundtrip"])])
        if (folder / "validate.py").exists():
            jobs.append((folder / "validate.py", []))
        if args.previews and (folder / "preview.py").exists():
            jobs.append((folder / "preview.py", []))
            if folder.name == "tensor":
                jobs.append((folder / "preview.py", ["--shield-preview"]))
        if args.showcases and (folder / "animate.py").exists():
            jobs.append((folder / "animate.py", []))
        rerun_downstream = False
        source_digest, sources = source_snapshot()
        report.setdefault("source_snapshots", {})[source_digest] = sources
        native_inputs = generated_inputs(folder)
        for script, arguments in jobs:
            relative = script.relative_to(ROOT).as_posix()
            key = relative + (" " + " ".join(arguments) if arguments else "")
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            previous = report["jobs"].get(key, {})
            output_hashes = previous.get("fresh_output_sha256", {})
            outputs_match = all((ROOT / name).is_file() and file_hash(ROOT / name) == value
                                for name, value in output_hashes.items())
            if (args.resume and not rerun_downstream and previous.get("passed") and
                    previous.get("script_sha256") == digest and
                    previous.get("source_snapshot_sha256") == source_digest and
                    previous.get("generated_dependency_sha256") == native_inputs and
                    "fresh_output_sha256" in previous and outputs_match):
                print("SKIP verified " + key, flush=True)
                continue
            rerun_downstream = True
            log = target / (relative.replace("/", "__") + "_" + "_".join(a.strip("-") for a in arguments) + ".log")
            command = [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script)]
            if arguments:
                command += ["--", *arguments]
            started = time.time()
            entry = {"command":command,"started":started,"script_sha256":digest,"log":str(log),"running":True,"passed":False}
            entry["source_snapshot_sha256"] = source_digest
            entry["generated_dependency_sha256"] = native_inputs
            entry["own_input_sha256"] = {p.relative_to(ROOT).as_posix(): file_hash(p)
                for p in sorted(folder.iterdir()) if p.is_file() and
                (p.suffix in {".blend", ".glb", ".fbx"} or p.name.endswith("_rig.json"))}
            report["jobs"][key] = entry
            report["active_job"] = key
            print("RUN " + key, flush=True)
            with log.open("w", encoding="utf8") as stream:
                child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                entry["process_pid"] = child.pid
                save(report_path, report)
                code = child.wait()
            output = log.read_text(encoding="utf8", errors="replace")
            entry.update(running=False, exit_code=code, seconds=round(time.time()-started, 2),
                passed=code == 0 and "Traceback (most recent call last)" not in output)
            entry["fresh_outputs"] = [str(p.relative_to(ROOT)) for p in folder.iterdir()
                if p.is_file() and p.suffix in GENERATED and p.stat().st_mtime >= started - 1]
            entry["fresh_output_sha256"] = {Path(name).as_posix(): file_hash(ROOT / name)
                                            for name in entry["fresh_outputs"]}
            entry["source_inputs_unchanged"] = source_snapshot()[0] == source_digest
            entry["passed"] = entry["passed"] and entry["source_inputs_unchanged"]
            save(report_path, report)
            print(("PASS " if entry["passed"] else "FAIL ") + key, flush=True)
            if not entry["passed"]:
                print(output[-2500:], flush=True)
                raise SystemExit(1)
    report.update(completed=True, active_job=None)
    save(report_path, report)
    print("REBUILD_LIBRARY_PASS assets=" + str(len(models)), flush=True)


if __name__ == "__main__":
    main()
