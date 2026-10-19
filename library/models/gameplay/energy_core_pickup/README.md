# Energy core pickup

A **10 × 10 × 10 cm hollow blue sphere**, with **5 mm radial walls** and
25% opacity. There is no base or corner support. The shell has concentric
50 mm outer / 45 mm inner radii, outward exterior normals and inward cavity
normals. Its origin is the centre for pickup sockets.

The inner solid lightning bolt reuses the current Energy Core's exact outline,
uniformly scaled to 40%: 5.2 cm wide × 7.6 cm high × 1.456 cm deep.
Its swept sphere clears the cavity by 5.64 mm. Blue shell and cyan emissive
bolt materials match the Energy Core. Shell surface effects remain for game shaders.

The same two rigid bones rotate horizontally about Blender +Z (Godot +Y):
`Outer` +360° and `Inner` −360°, in a continuous linear five-second `spin`
loop at 24 fps, frames 1–121. The authored mesh totals 2,452 triangles within
5K. There is no solid collider companion, matching the other core pickups.
until game integration is requested.

Run from library using the Blender executable specified in AGENTS.md:

```powershell
& $blender --background --factory-startup --python models/gameplay/energy_core_pickup/model.py
& $blender --background --factory-startup --python models/gameplay/energy_core_pickup/preview.py
& $blender --background --factory-startup --python models/gameplay/energy_core_pickup/validate.py
& $blender --background --factory-startup --python models/gameplay/energy_core_pickup/animate.py
```

Fresh GLB/FBX round trips check exact dimensions, radial wall thickness,
closed surfaces and their normal directions, UVs, rigid skinning, symbol
clearance, actual spin direction and loop closure. Generated exports,
previews, atlases and showcase video are ignored beside the source.
