# Cinematic captures

Each scene stages an encounter on the populated arena with a fixed camera,
starting positions and weapon loadouts. Simulation runs at **10% speed**. The
controller supplies aim and trigger inputs; the real weapon animation events,
projectiles, collisions, impacts, damage, knockback, deaths and Energy Core
creation produce the action. Effects and projectiles are not positioned by hand.
Free AI movement is disabled to preserve the composition. The aftermath plan
starts one target at 30 armor so a normal weapon hit can produce an elimination.

The damage-flash material overlay is hidden for photographs. Damage and native
hit reaction animations still run. Player settings and normal gameplay are not
changed by this presentation-only override.

Five capture plans are available per map:

| Plan | Location and starting weapons |
| --- | --- |
| Faceoff vista | Full crater outpost |
| Faceoff combat | Laboratory courtyard; rifle, flak and grenade launcher |
| Faceoff portal | Cistern interior; lightning and EMP |
| Faceoff aftermath | Floodlit cistern courtyard; minigun, pistol and grenade launcher |
| Faceoff launch | Jump-pad approach; flamethrower, bio rifle and pistol |
| Skyfall vista | Floating tiers, bridges and machinery |
| Skyfall combat | Lower bridge; rocket launcher, EMP and rifle |
| Skyfall portal | Lower-deck portal; lightning and EMP |
| Skyfall aftermath | Upper platform; minigun, pistol and grenade launcher |
| Skyfall launch | Lower-deck jump pad; flamethrower, bio rifle and pistol |

Run from `game/` using the custom engine and NVIDIA GPU:

```powershell
$Godot = '../engine/bin/godot.windows.editor.x86_64.console.exe'
& $Godot --path . --render-thread safe --gpu-index 0 tools/cinematics/faceoff_combat.tscn
& $Godot --path . --render-thread safe --gpu-index 0 tools/cinematic_showcase.tscn -- --map=skyfall
```

The first command captures one take; the second runs all five Skyfall plans.
Each take waits for the fixed view to become ready, starts its simulation clock,
begins firing at 0.6 simulated seconds, and pauses for readback at the chosen
instant. The capture time includes the pre-fire interval. Camera, actors and
map placements stay under explicit authoring control; shot outcomes use gameplay.

Captures use native 1920×1080 Ultra, DLSS Ray Reconstruction, **upscaling off**,
fixture illumination and shadows, and no HUD. The controller asserts native
viewport scaling and waits for renderer readiness before releasing the match
countdown. Camera exposure ranges from 1.15× to 1.6×. Audio is muted; player
preferences are neither loaded nor saved.

Use these arguments after `--`:

- `--preview=1`: native 1280×720 proof.
- `--shot=portal`: one capture plan.
- `--speed=0.1`: simulation speed (default 10%).
- `--capture-at=0.95`: capture time in simulated seconds from the take's start.
- `--out=res://reports/cinematics/custom`: output folder.

PNGs and metadata are written under ignored `game/reports/cinematics/`.
Metadata records the GPU, renderer readiness, internal resolution scale, speed,
exact capture time, actor state, weapons, shot counts, corpses and drops.
