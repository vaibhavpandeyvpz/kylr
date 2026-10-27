# Ramparts

`figma_layout.json` records the map hierarchy, layer transforms and native
footprints at 100 pixels per metre. `layout.py` converts that snapshot into
metre-based deck sections, fixture markers and machining specifications.
Blender uses +Z up and -Y forward; Godot coordinates are `(x, z, -y)`.

Floater 1 on each side carries a Bio Rifle and its matching ammo pickup.
Weapon labels match the longest weapon name first so Bio Rifle remains distinct
from Rifle.

`settings.json` owns the Martian daytime lighting recipe and orientation rules.
Its `excluded_assets` removes pole lights from all generated placements and
carrier sockets while preserving the raw Figma snapshot. Barricades and pressure plates rotate
90 degrees, including their native recesses. Containers rotate 90 degrees so
their fronts face the larger clear area; only `front_open` is enabled. Contained
repair bays rotate with the host and align their entry with its front doors.
The handoff writes the environment recipe into the runtime map catalog.
Platform sconces remain emissive-only through `platform_emissive_only_assets`,
with no projected light or mesh shadow casting, including in High quality.
Each team has two regular spawn hatches in its cistern and three exterior
stasis chambers facing inward. The two recessed hatches face each other, and
exterior chamber doors point at their cistern centre. These orientations also
own the machined recess frames. `architecture_variants.py` retains the native
cistern rig, actions and finishes while cutting stepped hatch recesses into
its render and collision floors. The terrain uses the same stepped recesses.
The source JSON also stops the sea-death camera at 1 m above water while its
look target continues to follow the falling corpse.

The 25 × 25 m rocky mainland plains, six 10 × 10 m floaters, two 15 × 15 m
side platforms and 22.5 m central cross start at 10 m above the lake.
The 25 m blueprint footprint is a protected summit core. Seeded, rounded
scallops extend into a roughly 1.4 m shoulder; shallow exposed-ground erosion
and a 0.65 m rim roll blend into stratified cliffs with closed bases at -17 m,
below the lake bed.
`terrain.py` builds one closed surface for rendering and collision, including
undercuts. Fixture seats stay level; all recesses cut the actual terrain.
`settings.json` owns the elevation and terrain recipe.
Floaters bob between 9.5 and 10.5 m above sea level.

Ramparts cliff, summit, platform and prop regolith slots bind a cached six-layer
Martian PBR material through the source catalog's `soil_material`. Dust, dunes,
bedrock, rubble, strata and lake sediment remain separate original sources.
Native industrial finishes remain authored. Original Imagegen albedos,
full prompts and deterministic periodic PBR bakes live in `textures/martian_soil`.
Rebuild the texture set with `.venv/Scripts/python.exe textures/martian_soil/generate.py`
before the game import. Normals and height are conservative image-derived
microrelief approximations. Dusty peach daylight, warm sunlight, ambient sky fill
and mineral water are configured alongside the terrain recipe.
The cross uses five Boolean-unioned rectangles from the blueprint.
The lake is a finite 150 m circular surface at 0 m, above a 15 m deep basin.
`crater_field.py` owns the Terrain3D height field and geological control masks;
`crater.py` closes and budgets the baked geometry and places 72 fractured stone
solids around the shoreline and mountain foot. Dunes, shelves and a continuous
eroded mountain rim are geometric landforms. Scenery remains outside the arena's
navigation bounds. The separate native scenery contains 46,160 terrain triangles
on a 4 m Terrain3D grid and 2,040 stone triangles, within its 60,000-triangle
scenery budget. The arena's integral geometry contains 19,695 triangles.
Decks use the shared native platform builder, original finishes and fixture
sockets. Native architecture, fixtures and thrusters import separately with
identity local transforms. Recessed fixtures use native footprints plus
1 mm clearance per side in render and collision machining.

The carrier rig owns deck-relative placement. Runtime gameplay samples its
seven moving bones from match elapsed time; the assembly action is independent.
Shuttles travel 7.5 m at 1 m/s with ±0.5 m bob at 1 m/s peak vertical speed.
The junction rotates clockwise at 0.5 m/s at its 11.25 m arm tip.
`floater_paths` names the two mainland-to-mainland itineraries through the
floaters and side islands. Bots stage each crossing one reachable deck at a time.

Run from `library/` with Blender 5.2 on PATH:

```powershell
./.venv/Scripts/python.exe textures/martian_soil/generate.py
./.venv/Scripts/python.exe tools/build_martian_terrain.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/ramparts/architecture_variants.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/ramparts/model.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/ramparts/collision.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/ramparts/validate.py
./.venv/Scripts/python.exe models/maps/ramparts/handoff.py
```

`model.py -- --shell-only` rebuilds the island/carrier rig while retaining
validated native platform variants.
`model.py -- --only-decks A_Island,B_Island` rebuilds selected platform variants
and the carrier rig, retaining the other validated variants.
`collision.py` exports the matching closed rock shells and nonblocking CTF
capture cylinders. Validation checks the geometry
budget, dimensions, finite coordinates, closed collision and all GLB/FBX round
trips. Handoff copies runtime exports and registers map data and five camera
shots. Capture the fully assembled map with the game's map-preview tool and
encode the five 1280 × 720 WebP photographs for the map-selection gallery.

Only integral islands, platform castings and machining count toward the
25,000-triangle map budget. Native imported assets retain separate budgets.
Handoff replaces embedded canonical regolith images with the shared runtime
textures and proves unchanged geometry, skinning, sockets and animation.
Builds, atlases, previews and validation reports remain ignored outputs.
