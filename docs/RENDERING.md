# Rendering

The game uses official Godot 4.7.2 with Forward+ raster rendering and Vulkan on
Windows. Windows CI installs Godot and matching export templates with
`chickensoft-games/setup-godot@v2`. Local setup and Linux container downloads
use `tools/prepare_godot.py` with SHA-512 pins from `tools/godot-release.json`.
`GODOT` or PATH selects the editor; local overrides stay outside source control.

## Graphics presets

Faceoff lava uses the opaque `lava.gdshader` material with an original Imagegen
molten-basalt texture. Slow advected crust and analytic surface-normal folds
produce flow without screen-color or depth-buffer refraction. Incandescent
channels and bubble bursts emit light through the existing glow pass. Sparse
instanced droplets and low-resolution geometric bubbles follow deterministic
match time, reduce detail with effect quality and stop under reduced motion.
Faceoff's ground, crater and mountains blend six original volcanic PBR layers.
Slope-based basalt exposure distinguishes steep rock from ash and slag deposits;
native soil aprons retain object-local projection. A low warm sun and softer
sky fill light the evening scene. Its static procedural sky uses cached quality
reflections. Skyfall caches its fixed reflection cubemap while the visible wisps
continue to use the background clock.

Low disables shadows, ambient occlusion, bloom and MSAA. Medium enables shadows,
bloom and 2× MSAA. High enables fixture illumination, shadows, ambient occlusion,
bloom and 4× MSAA. Low and Medium retain emissive-only fixtures. Custom preserves
individual settings, including optional 8× MSAA. All presets retain authored
ambient light, raster GI and reflection maps at native resolution.

Ramparts and Skyfall platform sconces retain their native emissive materials
without projected illumination or mesh shadow casting at every quality setting.
Their source map data sets `platform_emissive_only_assets`; these sconces create
no Light3D nodes, so applying High cannot restore their illumination. Interior
architecture lights and platform battens follow the normal preset rules.

Menu portraits use independent raster studios with native resolution and 4×
MSAA. Sconce and batten area lights and aimed pole/jumbotron spotlights follow
their native sockets. Separate rendering is experimental and defaults Off;
changing it requires restart and does not change quality preferences.

Game scripts use standard Godot APIs. Portal navigation
uses scripted costs and an admissible portal heuristic on `AStar3D`; visibility
queries use `PhysicsDirectSpaceState3D.intersect_ray`. Audio routes are fixed at
startup as defined in [audio](AUDIO.md).

## Geometry and shadow work

Opaque material sections share a shadow-only mesh with the same indexed vertices,
normals and skin weights. Visible native materials and meshes stay unchanged.
Transparent, custom-shader and grown surfaces retain their native shadow path.
Shadow batches share the source skin, transform, culling range and visibility;
robot debris caches their rigid fragments during loading. Fixed platform
castings use shared unskinned meshes while their parent carrier rigs bob.

## Verification

Ramparts blends six original 2048 px Martian PBR layers: dust, dunes, bedrock,
rubble, mountain strata and lake sediment. Albedo/height and OpenGL
normal/roughness pairs use 4 m repeat. Terrain3D height/deposit
fields, surface slope and water elevation select the layers; native stones use
a bedrock/strata blend. Source images and exact prompts live in
`library/textures/martian_soil`.
Terrain uses world-space geological mapping. Platform and prop deposits use
object-local projection, fixed mineral weights and the moving object's normal
basis, so translation, bobbing and rotation carry their texture details with them.
Ramparts uses a dusty peach Martian daytime sky, warm directional sunlight and
sky ambient fill from its generated map environment data. Pole lights are
excluded by its source placement recipe. Its original lake shader provides analytic swells,
per-fragment normals, depth absorption, guarded screen refraction, dielectric
reflection, shore foam and caustics. It uses no external water textures.
The circular water mesh has a 75 m radius, with displacement fading into the
buried shoreline. There is no distant water surface. Reduced
Motion freezes the cosmetic water clock, independently of moving deck gameplay.
The shader reconstructs depth separately for Forward+/Mobile and Compatibility.
Verify both paths with map captures; Forward+ on Vulkan is the shipping target.

Run import, GUT, match smoke checks and exported package inspection using the
same official release. Check menu and match appearance, moving fixtures, effects,
scene transitions and clean exit graphically. Headless checks do not establish
visual quality, audio quality or frame rates. [Playtesting](PLAYTESTING.md) owns
roster and performance qualification.
