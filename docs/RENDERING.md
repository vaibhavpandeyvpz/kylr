# Rendering

The game uses official Godot 4.7.2 with Forward+ raster rendering and Vulkan on
Windows. Windows CI installs Godot and matching export templates with
`chickensoft-games/setup-godot@v2`. Local setup and Linux container downloads
use `tools/prepare_godot.py` with SHA-512 pins from `tools/godot-release.json`.
`GODOT` or PATH selects the editor; local overrides stay outside source control.

## Graphics presets

Low disables shadows, ambient occlusion, bloom and MSAA. Medium enables shadows,
bloom and 2× MSAA. High enables fixture illumination, shadows, ambient occlusion,
bloom and 4× MSAA. Low and Medium retain emissive-only fixtures. Custom preserves
individual settings, including optional 8× MSAA. All presets retain authored
ambient light, raster GI and reflection maps at native resolution.

Menu portraits use independent raster studios with native resolution and 4×
MSAA. Sconce and batten area lights and aimed pole/jumbotron spotlights follow
their native sockets. Separate rendering is experimental and defaults Off;
changing it requires restart and does not change quality preferences.

Game scripts use standard Godot APIs. Portal navigation
uses scripted costs and an admissible portal heuristic on `AStar3D`; visibility
queries use `PhysicsDirectSpaceState3D.intersect_ray`. Audio routes are fixed at
startup as defined in [audio](AUDIO.md).

## Verification

Run import, GUT, match smoke checks and exported package inspection using the
same official release. Check menu and match appearance, moving fixtures, effects,
scene transitions and clean exit graphically. Headless checks do not establish
visual quality, audio quality or frame rates. [Playtesting](PLAYTESTING.md) owns
roster and performance qualification.
