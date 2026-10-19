# Shield core

Green variant of the [Energy Core](../energy_core/README.md), using the same
`energy_core/cube.py` generator. The only visual changes are a **solid 3D shield**
in place of the bolt and **green** outer/inner materials.

The chamfered hollow cube remains **25 cm**, with **5 mm walls**, **25% opacity**,
5 mm projecting corner cups, their fitted Boolean seats and the unified 15 mm
lower base. Complete hardware bounds remain **26 × 26 × 26 cm**. The origin is
at the centre. The shield measures 14 cm wide × 19 cm tall × 3.64 cm deep,
with bilateral symmetry, a raised top crest and tapered sides meeting a point.
Its swept sphere clears the cavity by 23.27 mm throughout counter-rotation.

`Outer` turns +360° and `Inner` turns −360° horizontally about Blender +Z
(Godot +Y) in the same continuous five-second `spin` loop, 24 fps, frames 1–121.
The green cube has no emission; game shaders can add surface effects later.
No solid collider companion is authored, matching Energy Core.

Run from library with the headless Blender executable specified in AGENTS.md:

```powershell
& $blender --background --factory-startup --python models/gameplay/shield_core/model.py
& $blender --background --factory-startup --python models/gameplay/shield_core/preview.py
& $blender --background --factory-startup --python models/gameplay/shield_core/validate.py
& $blender --background --factory-startup --python models/gameplay/shield_core/animate.py
```

Fresh GLB/FBX validation checks closed outward solids, exact assembly bounds,
5 mm wall planes, zero glass/support intersection, UVs, rigid skinning, green
shell colour, shield symmetry/clearance and actual spin direction/loop closure.
The asset has 840 triangles within the 5K budget. Generated exports, native
files, UV atlases, previews and video remain ignored. delivery.
