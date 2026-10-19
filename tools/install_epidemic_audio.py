"""Restore verified library clips and game cues using licensed Epidemic downloads."""
import argparse
import hashlib
import json
from pathlib import Path

from audio_pcm import mono48, read_pcm, wav_bytes
from download_epidemic_audio import CACHE, download
from epidemic_mcp import EpidemicMCP, ROOT

MANIFEST = ROOT / "library/sounds/epidemic_manifest.json"


def destination(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not name.startswith(("library/sounds/", "game/assets/audio/")):
        raise ValueError("Audio manifest path escapes the permitted folders")
    return path


def pcm_hash(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(path, digest, parameters=None):
    if not path.is_file():
        return False
    data, channels, width, rate = read_pcm(path)
    if parameters and (channels,width,rate) != parameters:
        return False
    return pcm_hash(data) == digest


def write_clip(path, data, digest, parameters, force):
    if pcm_hash(data) != digest:
        raise ValueError(f"Prepared PCM checksum differs: {path.name}")
    if checked_file(path,digest,parameters):
        return
    if path.exists() and not force:
        raise ValueError(f"Existing audio differs: {path}. Use --force to replace deliberately.")
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix(".partial")
    temporary.write_bytes(wav_bytes(data,*parameters))
    temporary.replace(path)


def render_cue(path, entry):
    import numpy as np
    source = np.frombuffer(mono48(path),dtype="<i2")
    first, frames = entry["start_frame"],entry["frames"]
    clip = source[first:first+frames].astype(np.float64)
    if len(clip) != frames:
        raise ValueError("Cue trim exceeds its source recording")
    count = entry["tail_frames"]
    mode = entry["tail_mode"]
    if count:
        if count > frames or mode not in ("fade","loop"):
            raise ValueError("Invalid cue tail recipe")
        ramp = (np.arange(count)+1)/count
        tail = clip[-count:]*(1-ramp)
        if mode == "loop":
            tail += clip[:count]*ramp
        clip[-count:] = tail
    return np.rint(clip).clip(-32768,32767).astype("<i2").tobytes()


def prepare(root=ROOT, offline=False, force=False, check=False):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if check:
        for group in ("library","game"):
            for entry in manifest[group]:
                if not checked_file(destination(root,entry["file"]),entry["pcm_sha256"]):
                    raise ValueError(f"Missing or changed local cue: {entry['file']}")
        print("PASS Epidemic library and game cues: exact PCM checksums")
        return
    client = None
    CACHE.mkdir(parents=True,exist_ok=True)
    for identifier,entry in manifest["sources"].items():
        path = CACHE / (identifier+".wav")
        parameters = entry["channels"],entry["sample_width"],entry["sample_rate"]
        if not checked_file(path,entry["pcm_sha256"],parameters):
            if offline:
                raise ValueError(f"Missing verified cached source {identifier}; download with your own account")
            if client is None:
                client = EpidemicMCP().connect()
            download(client,identifier,path)
            if not checked_file(path,entry["pcm_sha256"],parameters):
                raise ValueError(f"Downloaded source checksum differs: {identifier}")
    for entry in manifest["library"]:
        data,channels,width,rate = read_pcm(CACHE / (entry["source_id"]+".wav"))
        align = channels*width
        first = entry["start_frame"]*align
        data = data[first:first+entry["frames"]*align]
        write_clip(destination(root,entry["file"]),data,entry["pcm_sha256"],(channels,width,rate),force)
    for entry in manifest["game"]:
        data = render_cue(destination(root,entry["library_file"]),entry)
        write_clip(destination(root,entry["file"]),data,entry["pcm_sha256"],(1,2,48000),force)
    prepare(root,check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",action="store_true",help="Verify installed PCM without network access")
    parser.add_argument("--offline",action="store_true",help="Use only verified cached downloads")
    parser.add_argument("--force",action="store_true",help="Replace existing files that differ")
    parser.add_argument("--output-root",type=Path,default=ROOT,help="Alternative root for a clean-install check")
    args = parser.parse_args()
    try:
        prepare(args.output_root.resolve(),args.offline,args.force,args.check)
    except (ValueError,OSError,ImportError) as error:
        raise SystemExit(f"Epidemic audio: {error}") from None
