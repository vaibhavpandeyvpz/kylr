# Lunar regolith

Original shared 2K lunar PBR set. The canonical source image, generation prompt,
map builder and channel contract live in
[`library/textures/lunar_surface`](../../../../library/textures/lunar_surface/README.md).
Library and runtime copies are byte-identical tracked project assets.

`regolith_albedo.png` is sRGB. `regolith_normal.png` is OpenGL/linear.
`regolith_orm.png` is linear: red AO, green roughness, blue metallic (zero).
All three use mipmaps and VRAM compression. `Arena.finish_lunar_surface` assigns
them to the three lunar regolith roles at triplanar scale 0.24 per metre and
normal strength 0.55. Skyfall's moving platform deposits and architecture aprons
use object-local coordinates; the menu platform uses the same canonical set.
Skyfall's crater blends the planetary terrain layers. Ramparts uses its Martian
soil materials, and Faceoff uses its volcanic materials. The albedo is untinted,
including by vertex colors; AO is not baked into it. Native model exports refer
to this shared set instead of carrying a texture copy per model.
