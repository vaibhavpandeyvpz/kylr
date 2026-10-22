# Muzzle flame-flow material

Generated with OpenAI built-in imagegen in opaque image generation mode.

Production game VFX material texture, square seamless tileable grayscale scalar
flow/density map for wrapping a 3D muzzle flash. Fill the entire canvas edge to
edge with vertically flowing hot-gas filaments, feathered flame tongues,
turbulent thin curling ribbons and connected broader flame folds. Flow generally
from bottom toward top with irregular branching and wispy torn streaks at many
scales. Dark grey/black low-density gaps separate pale grey/white hot filaments,
with rich smooth midtones. Broad folds intermingle with very fine pointed
feathered threads. Continuous unlit material field, no isolated flame silhouette,
explosion ball, sprite sheet, rendered object, color, text, borders, grid or
directional baked lighting. Fully opaque grayscale, matching opposite edges,
strong but smooth density variation and organically curling irregular flow.

`export_muzzle_flow.py` derives matching linear hot-gas albedo/density and tangent
normal/roughness maps. The shader controls temperature, emission and erosion;
the maps describe gas filaments rather than a metallic surface finish.
