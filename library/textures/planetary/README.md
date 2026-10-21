# Planetary surface sources

`generate.py` builds six original 2048 px periodic PBR layers from ImageGen albedo sources: dust, basalt, bedrock,
rubble, compacted dust and impact scorch. Each 4 m tile has RGBA albedo/height
and RGBA OpenGL normal/roughness maps. The original images and exact generation prompts are retained in `sources/` and
`generation.json`. Periodic boundary correction and broad illumination removal
prepare the albedo. Image-derived microrelief supplies matching OpenGL normals,
height blending and roughness; this is an authored approximation, not measured scan
data. Normals derive from the metric gradient of that relief. All surfaces are nonmetallic.

Run from `library/`:

```powershell
.venv/Scripts/python.exe textures/planetary/generate.py
.venv/Scripts/python.exe tools/build_planetary_terrain.py all
.venv/Scripts/python.exe tools/test_planetary_field.py
```

The game owns the prepared PNGs and their hash manifest in
`game/assets/textures/planetary/`. Packed normals disable normal-map compression
so their roughness alpha survives. Images use high-quality VRAM compression
and mipmaps. Geological control maps are generated from the same source height
field as the terrain. The runtime shader height-blends the six layers and uses
dominant-axis projection on steep bedrock faces.
