# Shared map builders

- `platform/`: one dimensional platform builder with integral Boolean-unioned
  extensions, configurable perimeter border, optional tapered underbody, native
  fixture sockets and seeded surface regolith before placement cuts.
- `bridge/`: the native covered/railed bridge, its assembly/collision validation
  and preview scripts. Its structural paint matches the platform border.
- `map_shells.py`: shared 1 mm-per-side / 0.5 m-above-surface machining.
- `planetary_field.py`: deterministic height fields and geological material weights.
- `planetary_surface.py`: Terrain3D-baked landforms, stitched scenery and native fixture cuts.
- `lighting_preview.py`: native fixture beam direction/cone/range in Blender.
- `native.py`: headless bridge builder loading for map assembly.

Size-specific platform and lip helpers are retired. Maps import separate authored
architecture/gameplay/environment props on their native gizmos; only castings and
required machining belong to map-owned geometry.
