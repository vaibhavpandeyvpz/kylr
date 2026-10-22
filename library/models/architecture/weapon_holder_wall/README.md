# Weapon Holder Wall

Static mechanical architecture block, exactly **2 × 2 × 2 m**, with a
**1 × 1 m lodge roof service assembly** on top. Complete height is **2.285 m**.
Its generator is `../mechanical_mounts.py`. Materials come directly from the
existing `gameplay/item_table/model.py` palette: native off-white/grey paint,
matte black and stainless steel. No replacement colours or finish settings.
Block surfaces and both recessed service-well linings on each side use native
off-white paint; access plates use the existing
M_Joint stainless finish (metallic 1, roughness 0.2).
Real chamfered access plates, retained hex fasteners and recessed slot details
follow the platform family's service-door construction.

Origin is the floor centre, with +Z up and front −Y. Outer bounds are
X/Y ±1 m and Z 0..2 m. `WeaponHolderMount` is at (0,−1,1), with the holder's
native +Z facing out along wall −Y, +X across and +Y up the wall. Parent the
separate holder scene under the socket with an identity local transform.
Only this gizmo is exported; the holder geometry is imported only for previews.

The 1×1 m native holder patch fits a 1.002×1.002 m opening: **1 mm clearance
per side**. The closed recess follows the native pit depth plus 1 mm at its
back. The same aperture and depth are retained by the five convex collider
sections. The wall's sides have closed recessed service wells with supported
thermal lines and compression fittings. Lower mounting strakes remain. The top grooves are replaced by a centred
1 × 1 m version of `lodge/model.py equipment()`, including its formed shroud,
intake louvres, top grille, fastened flange, indicator and clamped conduit.
The original closed geometry is retained; the two collar/pedestal bearing
lands are fused for watertight delivery. The unit starts at Z 2 m and adds
0.28481 m. Collision includes a sixth convex proxy for the roof unit.

Run from `library/` with the Blender 5.2 executable specified in AGENTS.md:

```powershell
& $blender --background --factory-startup --python models/architecture/weapon_holder_wall/model.py
& $blender --background --factory-startup --python models/architecture/weapon_holder_wall/collision.py
& $blender --background --factory-startup --python models/architecture/weapon_holder_wall/validate.py
& $blender --background --factory-startup --python models/architecture/weapon_holder_wall/preview.py
```

Native GLB/FBX round trips audit dimensions, rigid Root weights, closed
casting surfaces, UVs, attachment positions and axes. The wall additionally
checks evaluated native holder geometry at all half frames of its five clips.
No animation is needed on these static castings. Exports, colliders, atlas
images and previews are ignored. Integrated into Skyfall as separate native imports on map placement gizmos.

Map integration uses native geometry/collision without scaling. Gizmo-only map
previews omit this prop; populated previews and runtime import it. Its triangles
are excluded from the map-owned casting budget.
