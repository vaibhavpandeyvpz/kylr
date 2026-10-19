# Baked skeleton mesh LOD check

Run `probe_baked_mesh_lods.gd` with this engine, a graphical rendering driver,
and an otherwise empty project. For example, pass an absolute script path with
`--path <project-directory> --script <script-path>`. Headless rendering does not
validate uploaded skin palettes.

The fixture creates a translated, single-bone quad with two imported LOD index
buffers. It waits for a rendered frame and checks the baked vertex positions,
base indices, removed skin attributes, exact LOD thresholds/index bytes, and
reuse of an existing output mesh. Success prints `BAKED_MESH_LODS` with
`passed: true` and exits zero. The original implementation fails the two LOD
checks because it discards the LOD dictionary when creating baked surfaces.

This validates topology/attribute preservation, not the visual quality of an
asset's authored LODs or a universal performance improvement. Skinning preserves
vertex order, so its LOD index buffers remain applicable to the baked vertices.
