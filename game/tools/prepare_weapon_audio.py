"""Prepare user-supplied weapon WAVs as compact, spatial-ready game assets.

Run with Python 3.10: python tools/prepare_weapon_audio.py --source ../library/sounds/weapons
The source directory is needed only while authoring; the game loads the copied output.
"""

from __future__ import annotations

import argparse
import audioop
import struct
import wave
from array import array
from pathlib import Path


OUTPUT_RATE = 48_000
WINDOW_SECONDS = 0.05
SILENCE_DB = -50.0
FRAME_BYTES = 2  # 16-bit mono


def read_pcm24(path: Path) -> tuple[bytes, int, int]:
    with path.open("rb") as file:
        if file.read(4) != b"RIFF":
            raise ValueError(f"Not a RIFF WAV: {path}")
        file.seek(12)
        channels = rate = bits = 0
        payload = b""
        while header := file.read(8):
            if len(header) != 8:
                break
            tag, size = struct.unpack("<4sI", header)
            if tag == b"fmt ":
                data = file.read(size)
                format_tag, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", data)
                if format_tag not in (1, 65534) or bits != 24:
                    raise ValueError(f"Expected 24-bit PCM: {path}")
            elif tag == b"data":
                payload = file.read(size)
            else:
                file.seek(size, 1)
            if size & 1:
                file.seek(1, 1)
    if not payload or channels not in (1, 2) or rate <= 0:
        raise ValueError(f"Incomplete WAV: {path}")
    return payload, rate, channels


def spatial_pcm(path: Path) -> bytes:
    source, rate, channels = read_pcm24(path)
    mono = audioop.tomono(source, 3, 0.5, 0.5) if channels == 2 else source
    resampled, _ = audioop.ratecv(mono, 3, 1, rate, OUTPUT_RATE, None)
    return audioop.lin2lin(resampled, 3, 2)


def active_windows(pcm: bytes) -> list[int]:
    window_bytes = int(OUTPUT_RATE * WINDOW_SECONDS) * FRAME_BYTES
    threshold = 10 ** (SILENCE_DB / 20.0)
    return [
        index
        for index, offset in enumerate(range(0, len(pcm), window_bytes))
        if audioop.rms(pcm[offset:offset + window_bytes], 2) / 32767.0 >= threshold
    ]


def trim(pcm: bytes) -> bytes:
    active = active_windows(pcm)
    if not active:
        raise ValueError("Clip contains no audible samples")
    start = max(0, int(active[0] * WINDOW_SECONDS * OUTPUT_RATE) - int(0.01 * OUTPUT_RATE))
    end = min(len(pcm) // FRAME_BYTES, int((active[-1] + 1) * WINDOW_SECONDS * OUTPUT_RATE) + int(0.08 * OUTPUT_RATE))
    return pcm[start * FRAME_BYTES:end * FRAME_BYTES]


def split_pistol_impacts(pcm: bytes) -> list[bytes]:
    active = active_windows(pcm)
    groups: list[tuple[int, int]] = []
    first = previous = active[0]
    for index in active[1:]:
        if index - previous > 6:  # At least 300 ms of silence separates authored variants.
            groups.append((first, previous))
            first = index
        previous = index
    groups.append((first, previous))
    if len(groups) != 3:
        raise ValueError(f"Expected three separate pistol impacts, found {len(groups)}")
    output = []
    for first, last in groups:
        begin = max(0, int(first * WINDOW_SECONDS * OUTPUT_RATE) - int(0.01 * OUTPUT_RATE))
        end = min(len(pcm) // FRAME_BYTES, int((last + 1) * WINDOW_SECONDS * OUTPUT_RATE) + int(0.08 * OUTPUT_RATE))
        output.append(pcm[begin * FRAME_BYTES:end * FRAME_BYTES])
    return output


def smooth_end(pcm: bytes, looping: bool) -> bytes:
    samples = array("h")
    samples.frombytes(pcm)
    seam = min(len(samples) // 4, int(0.08 * OUTPUT_RATE))
    if looping:
        # Blend the last 80 ms into the opening so the loop boundary is continuous.
        for index in range(seam):
            blend = (index + 1) / seam
            tail_index = len(samples) - seam + index
            samples[tail_index] = round(samples[tail_index] * (1.0 - blend) + samples[index] * blend)
    else:
        for index in range(seam):
            tail_index = len(samples) - seam + index
            samples[tail_index] = round(samples[tail_index] * (1.0 - (index + 1) / seam))
    return samples.tobytes()


def write_wav(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(FRAME_BYTES)
        file.setframerate(OUTPUT_RATE)
        file.writeframes(pcm)
    print(f"{path}: {len(pcm) / (OUTPUT_RATE * FRAME_BYTES):.2f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("assets/audio/weapons"))
    parser.add_argument("--only", nargs="+", help="Prepare only these source stems")
    args = parser.parse_args()
    continuous = ("lightning_gun_primary", "flamethrower_primary")
    secondary = ("lightning_gun_secondary", "flamethrower_secondary")
    for family, names in (
        ("shots", ("pistol", "rifle", "minigun", "rocket_launcher", "emp_gun", *continuous, *secondary)),
        ("hits", ("pistol", "rifle", "minigun", "rocket_launcher", "emp_gun", *continuous, *secondary, "shield")),
    ):
        for name in names:
            if args.only and name not in args.only:
                continue
            pcm = spatial_pcm(args.source / family / f"{name}.wav")
            if family == "hits" and name == "pistol":
                for index, variant in enumerate(split_pistol_impacts(pcm), 1):
                    write_wav(args.output / family / f"{name}_{index:02d}.wav", smooth_end(variant, False))
                continue
            # Blend primary loop seams; retain secondary attacks/tails trim-only.
            processed = smooth_end(trim(pcm), True) if name in continuous else trim(pcm) if name in secondary else smooth_end(trim(pcm), False)
            write_wav(args.output / family / f"{name}.wav", processed)


if __name__ == "__main__":
    main()
