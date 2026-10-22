# Planetary terrain

Faceoff and Skyfall use deterministic height fields baked with Terrain3D, then
machined and exported through the Blender map generators. The game and dedicated
server load static render and collision meshes. They do not load Terrain3D's
native extension or generate terrain during a match.

## Shape and gameplay

`library/models/maps/common/planetary_field.py` owns the height fields and six
geological material weights. Faceoff has graded cover banks, shallow channels,
excavated building seats and a broken impact rim. Native architecture, doors,
lift approaches, spawn mechanisms and pickup footprints retain their placement
datum. Foundation masks come from the source layout and native footprint metadata.
The lander's complete deployed footprint, including its four pads and ladder
shoes, has a level seat with a grid-diagonal margin so interpolated terrain
triangles meet the feet at their native ground plane.
Bot sampling includes the full playable height range, with physical checks for
continuous slopes up to 40 degrees; larger steps and gaps remain separate traversal
actions. These checks run during graph construction, not every frame.
The playable area remains 75 × 75 m, bounded by walls at ±37.5 m. Distant scenery
is excluded from the navigation bake using the catalog's route bounds.

Skyfall floats over a depressed impact basin with fissures and secondary impacts.
Decks remain at 22/26/30 m; lunar contact remains lethal and is excluded from
navigation. Its void boundary is -20 m, below the deepest basin, so terrain
contact retains the lethal-ground impact behavior. Neither map moves fixtures to accommodate terrain. Recesses retain
the native footprint plus 1 mm clearance on each side.

Height samples cover 512 × 512 m at 1 m spacing. Terrain3D bakes the central
128 × 128 m at 1 m spacing and the outer landscape at 4 m spacing. The mesh
builder stitches the resolution boundary, trims the distant circular footprint,
and closes the volume with a vertical 2 m underside. Blender performs the native
fixture cuts and creates non-overlapping painting UVs. Render and collision
companions derive from the same source geometry.

## Materials

Six original ImageGen-derived 2048 px, 4 m periodic PBR layers are dust, basalt, bedrock, rubble,
compacted regolith and scorch. Albedo RGB is sRGB with linear height in alpha;
OpenGL normal RGB and roughness alpha remain linear. Exact prompts and original
albedo sources are retained under `library/textures/planetary/`. Periodic filtering
removes boundary discontinuities and broad illumination drift. Height and normals
are conservative image-derived microrelief approximations, not scan measurements. Normal-map compression is
disabled to preserve the packed roughness channel. Imports use mipmapped HQ VRAM
compression. Two RGB control maps per arena store the six geological weights.
Dust, exposed basalt, bedrock bands and loose rubble form metre-scale patches
with dominant interiors and irregular blended edges. Compacted regolith marks
Faceoff's disturbed fixture ground; localized scorch marks lander exhaust and
Skyfall's impact pit. The controls preserve material contrast rather than mixing
small amounts of every layer across the entire surface.

`game/shaders/original/planetary_terrain.gdshader` blends weights with layer height,
projects steep faces along their dominant axis and performs no vertex displacement.
Terrain chunks share one cached material per map. Platform tops and architectural
aprons retain their canonical lunar material. The handoff strips unused embedded
fallback textures while asserting unchanged geometry, UVs, skinning and animation.

## Rebuild

Run from `library/` with the local Python environment and Blender 5.2 on PATH:

```powershell
.venv/Scripts/python.exe textures/planetary/generate.py
.venv/Scripts/python.exe tools/build_planetary_terrain.py all
blender --background --factory-startup --python-exit-code 1 --python models/maps/faceoff/model.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/faceoff/collision.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/faceoff/validate.py
blender --background --factory-startup --python-exit-code 1 --python models/maps/faceoff/preview.py
```

For blend-control changes alone, run
`.venv/Scripts/python.exe tools/build_planetary_terrain.py all --materials-only`.
This path rejects height changes against the runtime manifest and leaves meshes
and collision untouched. Import and inspect both maps in the official Godot 4.7.2 after
changing the controls; refresh map-selection captures to match the runtime material.

Prepare native dependencies and architecture/platform variants as specified by
each map's README before rebuilding its map model. Repeat the four Blender stages
for Skyfall, inspect all previews and round-trip validation, then run:

```powershell
.venv/Scripts/python.exe tools/handoff_planetary_terrain.py
.venv/Scripts/python.exe tools/test_planetary_field.py
.venv/Scripts/python.exe tools/audit_game_handoff.py --report .local/planetary/handoff-audit.json
```

The bake helper installs the pinned MIT Terrain3D `v1.0.2-stable` SDK into ignored
`library/.local/terrain3d/`. Its release archive SHA-256 is
`a071850250ec5e596aa54da61c01d75768774eb379ee997584d426a45f4884a2`.
`GODOT_EXECUTABLE` or `--godot` may select the workspace's official Godot 4.7.2. Bake
caches stay in `.local/planetary/`; SDKs and generated library exports stay out of
Git. Runtime textures, control maps, their manifest and prepared game meshes are
checked in. The Terrain3D MIT notice ships with packaged licenses.

After handoff, run official Godot import, tests, physical source-height checks,
the complete two-map bot roster matrix, repeated CPU profiling and serial
rendered High comparisons under [playtesting](../PLAYTESTING.md). Refresh
map-selection and cinematic captures from fully populated runtime maps. Headless
route checks do not qualify rendering performance or appearance.
