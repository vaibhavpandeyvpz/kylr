# In-game cinematic gallery

Three arenas, three planetary settings. These fifteen staged encounters are
captured in Godot with the game's authored geometry, robot models, weapons and
effects at High quality, native 1920×1080, with upscaling off.

| Ramparts — Martian lake valley | Skyfall — lunar crater | Faceoff — volcanic world |
| --- | --- | --- |
| **Lake valley arena** — rocky summits, moving platforms and mineral water.<br>![Ramparts lake valley](media/cinematics/ramparts-vista.webp) | **Floating arena** — tiers, bridges, thrusters and lunar craters.<br>![Skyfall floating arena](media/cinematics/skyfall-vista.webp) | **Volcanic outpost** — burnt terrain, glowing lava pits and architecture.<br>![Faceoff volcanic outpost](media/cinematics/faceoff-vista.webp) |
| **Rotating junction** — rocket, EMP and rifle crossfire above the lake.<br>![Ramparts junction combat](media/cinematics/ramparts-combat.webp) | **Bridge confrontation** — rocket, EMP and rifle encounter.<br>![Skyfall bridge combat](media/cinematics/skyfall-combat.webp) | **Laboratory firefight** — rifle, flak and grenade encounter.<br>![Faceoff laboratory firefight](media/cinematics/faceoff-combat.webp) |
| **Cistern breach** — lightning and EMP at the mainland stronghold.<br>![Ramparts cistern breach](media/cinematics/ramparts-portal.webp) | **Portal defense** — electrical weapons on the lower deck.<br>![Skyfall portal defense](media/cinematics/skyfall-portal.webp) | **Cistern breach** — electrical weapons inside the portal chamber.<br>![Faceoff cistern portal](media/cinematics/faceoff-portal.webp) |
| **Island engagement** — minigun fire on the side platform.<br>![Ramparts island engagement](media/cinematics/ramparts-aftermath.webp) | **Upper-platform engagement** — minigun fire above the lower decks.<br>![Skyfall upper-platform engagement](media/cinematics/skyfall-aftermath.webp) | **Courtyard engagement** — minigun fire beside the cistern.<br>![Faceoff courtyard engagement](media/cinematics/faceoff-aftermath.webp) |
| **Mainland crossfire** — flame, bio and pistol fire near the jump-pad route.<br>![Ramparts mainland crossfire](media/cinematics/ramparts-launch.webp) | **Deck crossfire** — flame and bio weapons beside the jump pad.<br>![Skyfall deck crossfire](media/cinematics/skyfall-launch.webp) | **Jump-pad crossfire** — flame, bio and pistol fire on burnt ground.<br>![Faceoff jump-pad crossfire](media/cinematics/faceoff-launch.webp) |

The README hero combines three portrait captures, each with ten distinct
head/body/color combinations and all ten weapons. Its source portraits are
[Ramparts](media/heroes/ramparts.webp), [Skyfall](media/heroes/skyfall.webp) and
[Faceoff](media/heroes/faceoff.webp). The collage has no text overlays.

## How the captures work

Camera positions, cast placement and loadouts are staged. Shooting runs at 10%
simulation speed through the normal weapon, collision, damage and animation
systems. The selected instant is then paused for readback. Projectiles, beams,
impacts and deaths come from gameplay; they are not painted into the images.
The temporary damage-flash overlay is hidden for the photographs.

Portraits render to a native 1280×1920 offscreen viewport. Gallery frames render
at 1920×1080 and are compressed to 1280×720 WebP. The landscape hero combines
three 1024×1536 portraits with narrow gutters. Only compressed WebP media is
installed in this gallery; PNG originals and capture metadata stay in ignored reports.

See [the capture plans and commands](../game/tools/cinematics/README.md) to
recreate the scenes, change their framing or regenerate the media.
