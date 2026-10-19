# Workstation

Static standing industrial console, authored in metres by `model.py` with
Blender 5.2. No animation actions or showcase are authored.

The origin is the floor centre, +Z is up, and the active screens face **−Y**.
The visual bounds are **1.50 × 0.856 × 1.657 m**, including the retained rear
service cable. The desk itself is 1.50 × 0.80 m. The 1.053 m keyboard surface
and 1.438 m main-screen centre are proportioned against Tensor's 1.753 m height.
The auxiliary screen tilts 28° upward toward a standing operator. Both monitor
mounts are fixed welded brackets with broad seated mounting pads. The main
display is curved on a **1.50 m radius**, including its shell, bezel, seal, LCD
and glazing. Its neck stays behind the housing and meets a bolted, fitted rear
saddle. Power and signal run inside the hollow supports.

The load path is floor shoes → pierced lofted side castings → rear cabinet
and console shroud → display pedestals → rear display mounting pads. The side
armour has flush service inserts, captive fasteners and real through apertures.
The lower aperture and upper service insert have the same triangular profile,
related by a half turn: nominal fore/aft rails are 100 mm, top/bottom rails are
120 mm, and the diagonal web stays wider than 110 mm. Their chamfered ends and
shared geometry keep the borders and spacing consistent on both sides.
The console carries a seated operator cassette, 60 sealed keys, twin joysticks
with boots and metal stalks, rotary controls, a recessed cable-raceway cover,
and turquoise status indicators. A removable rear equipment hatch and front
intake cartridge provide service access and cooling. The visible cable joins
two gland seats; its loop stays clear of the housing.

The asset uses the silhouette and mechanical furniture language.
Native off-white and grey paint, matte black, stainless steel and restrained
turquoise emission match the existing props. Surfaces use clean paint and metal finishes. Both displays use the sibling roof display's
original Python-generated service telemetry texture, packed inside the exports.
The two `SK_WorkstationScreen*` inserts use `M_Screen`, analytic UV0 and a unique
painting atlas on UV1. Each replaces its backer's front face to prevent z-fighting.
All visible geometry is rigidly weighted to one fixed `Root` bone.
`SK_WorkstationGlass` / `M_Glass` provides blue **10% opacity** glazing on both
displays: a **10 mm air gap** ahead of each LCD and a **2 mm pane**, supported by
the seal and recessed behind the bezel. Glazing is separated from the opaque
visibility cull. Its housing supplies collision.

Run from `library/`:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/environments/workstation/model.py
& $blender --background --factory-startup --python models/environments/workstation/preview.py
& $blender --background --factory-startup --python models/environments/workstation/inspection.py
& $blender --background --factory-startup --python models/environments/workstation/collision.py
```

`model.py -- --draft` keeps the solid-volume and connectivity audits but skips
the final visibility cull, UV packing and exports. The normal build writes
`.blend`, `.glb`, `.fbx`, `_rig.json`, the packed display texture and UV guides.
Generated files remain ignored. `preview.py` and `collision.py` are the shared,
model-agnostic prop scripts. `collision_extras.py` excludes screen and glass inserts
because their solid housings already supply collision.
`inspection.py` adds the three-quarter hero image and a side-by-side scale
comparison with the actual authored Tensor, without saving him into the asset.

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
