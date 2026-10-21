# Lunar regolith PBR

This original shared surface covers platform deposits, architecture aprons and
the menu platform. Map landscapes use the [planetary PBR layers](../planetary/README.md). The original
albedo source was generated with OpenAI Imagegen without third-party image inputs.
The source image, generation prompt and deterministic PBR builder are included.
These textures are included project assets; no external texture download is required.

## Maps and scale

All three runtime maps are 2048 x 2048 RGB PNGs. One repeat spans 4.1667 metres
(world triplanar scale 0.24). Every graphics preset uses the same set:

- `regolith_albedo.png`: sRGB mineral colour, periodic boundary correction.
- `regolith_normal.png`: linear OpenGL tangent normals; conservative, image-derived
  shallow relief. This is an authored approximation, not measured displacement.
- `regolith_orm.png`: linear R occlusion, G roughness (0.8-0.98), B metallic (zero).

Normal derivatives and cavity occlusion use periodic filters, avoiding wrap seams.
AO remains separate from the albedo. The source does not supply physical height
or terrain collision. The shared material applies normal strength 0.55.

## Rebuild and validate

Install `tools/requirements-assets.txt` in the
Python environment. From `library/`:

```powershell
& .venv/Scripts/python.exe textures/lunar_surface/generate.py
& .venv/Scripts/python.exe textures/lunar_surface/generate.py --check
```

The builder writes identical library/runtime maps and records hashes in `maps.json`.
It checks map size, unit normals, zero metallic and boundary continuity. Source
and runtime textures are intentionally tracked asset exceptions. Generated model
exports reference runtime maps externally. Native Blender generators and the hero
renderer refresh the canonical texture bytes when building materials.

Validate both populated maps from `game/`:

```powershell
& ../engine/bin/godot.windows.editor.x86_64.console.exe --path . --render-thread safe --gpu-index 0 --script tools/audit_regolith_materials.gd -- --capture
```
