# Cinematic captures

The capture controller stages encounters in the real Godot arenas. Camera,
cast positions and loadouts live in [plans.json](plans.json). It supplies aim
and trigger inputs at 10% simulation speed; native weapon animations,
projectiles, collisions, impacts and damage produce the action. Free bot movement
is disabled for composition. Unselected actors have their collision layer disabled.

The five gallery plans per map are `vista`, `combat`, `portal`, `aftermath` and
`launch`. Ramparts covers its Martian lake valley, rotating junction, mainland
cistern, island outpost and jump-pad approach. Skyfall covers its lunar floating
tiers, bridges, portals and upper decks. Faceoff covers its volcanic outpost,
laboratory, cistern and courtyard. The `portal` slot on Ramparts is a cistern
breach, not a portal mechanic.

The separate `hero` plan uses ten distinct head/body/color combinations and all
ten weapons on each map. Actors fire at authored world targets to expose native
weapon effects. Continuous flame and lightning streams are recorded separately
from discrete shot counts. Actor bounds are fitted within the portrait camera.
Robot palettes apply only to their armor; weapon and ammo paint retain their
authored asset colors, checked against the imported materials at capture time.
The hero triptych contains no text overlays or caption.

## Generate the README and gallery

Run from `library/` with the library Python environment and official Godot 4.7.2
resolved through `GODOT` or `--godot`:

```powershell
# Small portrait proofs; inspect before the final render.
& .venv/Scripts/python tools/render_hero_showcase.py --preview --hero-only

# Three full-resolution portraits plus all fifteen gallery scenes, compressed.
& .venv/Scripts/python tools/render_hero_showcase.py
```

The script validates all ten hero loadouts, distinct appearances, active weapons,
High quality, native resolution scale, rendering device and renderer readiness. It
keeps PNGs, metadata and logs in ignored `game/reports/cinematics/readme/`.
Compressed portraits go to `docs/media/heroes/`, gallery images to
`docs/media/cinematics/`, and the landscape collage to `docs/media/hero-showcase.webp`.
Use `--install-only` to recompress existing captures, `--input` for a capture
folder, or `--maps ramparts` for a single map.

## Capture individual scenes

Run from `game/`:

```powershell
& $env:GODOT --path . --render-thread safe --gpu-index 0 tools/cinematics/ramparts_combat.tscn
& $env:GODOT --path . --render-thread safe --gpu-index 0 tools/cinematic_showcase.tscn -- --map=skyfall
& $env:GODOT --path . --render-thread safe --gpu-index 0 tools/cinematic_showcase.tscn -- --map=faceoff --shot=hero
```

Arguments after `--`:

- `--map=ramparts`: select Ramparts, Skyfall or Faceoff.
- `--shot=portal`: select one plan; `all` captures the five gallery plans.
- `--preview=1`: 1280×720 gallery proof or 640×960 portrait proof.
- `--speed=0.1`: simulation speed, default 10%.
- `--capture-at=1.25`: simulated capture time, including the pre-fire interval.
- `--out=res://reports/cinematics/custom`: output folder.

Final gallery frames use native 1920×1080 High rendering, fixture illumination
and shadows, upscaling off and no HUD. Portraits use a shared-world 1280×1920
SubViewport with an on-screen proof, so desktop dimensions do not constrain
render resolution. Audio is muted. Player preferences and gameplay settings
are not loaded or saved. Metadata records the GPU, readiness, dimensions,
internal scale, capture time, appearances, weapon states, corpses and drops.
