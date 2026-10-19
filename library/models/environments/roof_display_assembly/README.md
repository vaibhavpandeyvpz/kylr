# Roof display assembly

Static ceiling-mounted twin industrial displays, authored entirely by `model.py`.
Screens face Blender **−Y**, up is +Z, and the origin is the centre of the
ceiling mounting plane at z=0. All geometry hangs below that plane.

The assembly is approximately **1.466 × 0.38 × 1.035 m**. Each active display
is **0.590 × 0.331875 m** (16:9, about 27 inches diagonally), proportioned against
Tensor's 1.753 m height. The structural finishes retain the library's native
off-white/grey paint, matte black and stainless steel. No team presets or
animations are authored; all parts are rigidly weighted to a fixed Root bone.

The load path is ceiling anchor plate → welded downstands and service rail →
clamped clevises → bored through pins and retaining caps → cast mounting tongues
and feet → lofted display shells. The rear covers have integral cooling ribs.
Both ends of each signal/power loom terminate on real gland seats. Outer service
handles have two feet seated on the housing's side flat. Boolean unions produce
single manufactured parts; separate parts meet on shared seats without overlapping
solid interiors. The ceiling-contact surface and invisible mating faces are culled.

The two screens are their own `SK_RoofDisplayScreen1/2` meshes, using `M_Screen`
with an **embedded original image texture** generated in Python. UI marks are
texture pixels, never individual mesh faces. Screen UV0 remains analytic 0..1;
the material painting atlas is on UV1. The screen surface replaces the backer's
front face to avoid coplanar rendering artifacts.

`SK_RoofDisplayGlass` / `M_Glass` supplies **blue, 10% opacity** protective glazing.
Its inner surface is **10 mm in front of the screen**; the pane is 2 mm thick,
supported by the surrounding seal and recessed 2 mm behind the bezel lip.
Glazing is separated before the opaque visibility cull. Glass and display inserts
share the housing's collision rather than adding duplicate collision surfaces.

Run from `library/`, using Blender 5.2 as specified in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/environments/roof_display_assembly/model.py
& $blender --background --factory-startup --python models/environments/roof_display_assembly/preview.py
& $blender --background --factory-startup --python models/environments/roof_display_assembly/collision.py
```

The generator rejects non-manifold manufactured parts, disconnected hardware,
solid-volume intersections and an aggregate visual budget above 5,000 triangles.
It validates unique 2048px material atlases before writing `.blend`, `.glb`,
`.fbx`, and `_rig.json`. `-- --draft` skips the final visibility cull and exports.
Generated outputs remain ignored.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.

## Cable routing

Service cables use the shared constant-radius sweep with circular elbows
and parallel-transported frames in `roof_display_assembly/model.py`. Each ring
is normal to the true path tangent and stays at the authored 6 mm radius.
Closed geometry, connectivity, solid-overlap and UV checks, plus fresh GLB/FBX
round trips pass after regeneration. Studio previews are refreshed.
