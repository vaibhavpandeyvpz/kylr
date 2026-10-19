"""Render Tensor's showreel: every clip of his animation library, one after another.

Run headless from the repo root (after model.py and animations/retarget.py):
    blender --background --factory-startup --python models/characters/tensor/animate.py [-- --no-render]

The clips are the retargeted library in animations/target (see animations/retarget.py): Tensor's own clips
(idle, falls, landing, deaths, defeat, the victory dances), then each weapon family's stance clips (rifle,
heavy, pistol and carry: idles, 8-way walk, run, sprint and crouch walk, turns, jumps, fire, reload, hit
reaction, grenade toss, deaths) shown without the weapon, as if he held one. Each clip is captioned; short
loops play twice. The weapons' own reels (their animate.py) show him holding each weapon. The reel is
rendered in the previews' studio to tensor_showcase.mp4; --no-render lays it out and stops.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "animations"))
import showreel  # noqa: E402

OUT_PATH = HERE / f"{HERE.name}_showcase.mp4"


def main():
    clips, man = showreel.tensor_clips()
    showreel.render(clips, man, OUT_PATH, "TENSOR", dry="--no-render" in sys.argv)


if __name__ == "__main__":
    main()
