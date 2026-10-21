# Planetary PBR assets

Original ImageGen albedo sources and exact prompts are retained in
`library/textures/planetary/`. The periodic PBR maps are built by `library/textures/planetary/generate.py`.
Each 2048 px 4 m tile contains sRGB RGB albedo with linear height alpha, and linear
RGB OpenGL normal with roughness alpha. Height/normal detail is an authored
image-derived approximation, not measured scan data. No metallic surface or baked directional
lighting is used. Keep packed normals' `compress/normal_map=2` import setting.

The 512 px map-specific weight images cover world X/Z from -256 m to +256 m.
They are linear data, divided into dust/basalt/bedrock and
rubble/compacted/scorch channels. `manifest.json` records texture hashes, source
height hashes, height ranges and physical QA sample points. Rebuild weights and
meshes together with `library/tools/build_planetary_terrain.py`.

`PlanetaryTerrain` shares one immutable material per map. Its shader modifies
surface shading, not vertex positions. The visible landform and collision both
come from the Terrain3D/Blender authoring pipeline. Terrain3D's SDK is not needed
to run the game or dedicated server.
