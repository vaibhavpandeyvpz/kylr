"""Convert the curated environment, locomotion, UI, and weapon utility WAVs.

Run with the project Python 3.10 virtual environment:
    ../library/.venv/Scripts/python.exe tools/prepare_world_audio.py --source ../library/sounds
"""

from __future__ import annotations

import argparse
from pathlib import Path

from prepare_weapon_audio import smooth_end, spatial_pcm, trim, write_wav


CLIPS = {
    "gameplay/barricade_close": "world/barricade_close",
    "gameplay/barricade_open": "world/barricade_open",
    "gameplay/pickup_item": "world/pickup_item",
    "gameplay/portal_enter": "world/portal_enter",
    "gameplay/portal_exit": "world/portal_exit",
    "gameplay/repair_ready": "world/repair_ready",
    "gameplay/repair_start_stop": "world/repair_start_stop",
    "gameplay/repair_weld": "world/repair_weld",
    "environment/thruster": "world/thruster",
    "locomotion/jump_land": "world/jump_land",
    "locomotion/jump_pad_launch": "world/jump_pad_launch",
    "locomotion/walk": "world/walk",
    "ui/interface": "world/interface",
    "weapons/other/pickup_ammo": "world/pickup_ammo",
    "weapons/other/pickup_weapon": "world/pickup_weapon",
    "weapons/other/reload": "world/reload",
}
LOOPS = {"world/repair_ready", "world/repair_weld", "world/thruster", "world/walk"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("assets/audio"))
    parser.add_argument("--repair-only", action="store_true", help="Prepare only the three repair recordings")
    args = parser.parse_args()
    for source, destination in CLIPS.items():
        if args.repair_only and not destination.startswith("world/repair_"): continue
        pcm = trim(spatial_pcm(args.source / f"{source}.wav"))
        write_wav(args.output / f"{destination}.wav", smooth_end(pcm, destination in LOOPS))


if __name__ == "__main__":
    main()
