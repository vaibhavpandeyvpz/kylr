# Engine guidelines

The engine component is an open-source Godot fork. It is distributed for use
by unrelated applications and must remain usable without any particular game.

## Project-neutral implementation and language

- Use engine-level terminology in source, API/class names, comments, documentation,
  diagnostics, environment variables, configuration keys and build metadata.
  Do not use a consuming game's name or branding for engine features or tooling.
- Describe the general capability or problem being solved. Keep game-specific
  presets, assets, maps, weapon rules, balance, performance targets and scene
  assumptions in the consuming application, not in this component.
- Keep renderer and physics changes reusable. Do not introduce dependencies on
  the game component, its scripts, filesystem layout or runtime state.
- LOD and rendering-distance decisions must use conservative world-space
  geometry bounds, including animated extents, rather than model origins.
  Levels must share a stable geometry envelope; use hysteresis around switches.
- Engine build instructions and tools must work from this repository with
  configurable dependency paths; do not require a particular consumer checkout.
- Preserve accurate upstream/vendor names and third-party licenses. Project
  neutrality does not mean renaming Godot, NVIDIA SDKs or their APIs.
- Use generic fixtures for engine tests. Application integration tests belong
  to the consuming application's repository. Record what was actually tested;
  do not present one application's results as universal compatibility claims.

## Changes and validation

Inspect existing changes and preserve unrelated work. Follow Godot's existing
style and subsystem conventions. Keep optional SDK integrations optional, with
explicit capability checks and clear unsupported-platform behavior. Validate
affected builds and runtime paths; distinguish correctness checks from visual
quality and performance qualification. Do not include generated builds, reports,
local SDKs or secrets in commits.
