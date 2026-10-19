# Lunar dome

Architecture with a hinged pressure/service door, within a
**6 × 6 × 3.16 m** siting envelope. Trimming the entrance's floor crescent makes
the exact closed depth 5.996 m; the canopy radii remain unchanged. The spherical canopy has equal
horizontal and vertical radii of **2.92 m**, centred at z = 0.18 m. Floor top
is z = 0.10 m; maximum interior ceiling clearance is **2.95 m**. The circular
foundation is 6 m across. Origin is at ground centre, front −Y, up +Z.

Uniform XYZ scaling is enforced in `architecture/dimensions.py`. Never use
vertical-only resizing on this hemisphere. Any future scale change must
also update pivots, slide travel, colliders and dimensional/traversal checks.

The glazed lunar habitats in user photos 2–4 inform the hemispherical canopy,
radial ribs, glazing courses, solid collar and attached entrance. KYLR's native
off-white/grey paint, matte black seals and stainless hardware surround
blue-grey glazing with exported alpha 0.32. The interior remains empty.

## Manufactured interfaces and rig

- Twenty radial ribs and four glazing courses form a continuous loft. Pane
  boundaries, sealing bevels and ribs share mesh vertices. Frame depth is
  45 mm; panes are recessed 8 mm on each side, with 11 mm sealing lands.
  Ribs terminate in the integral crown and foundation.
- The lofted, chamfered entrance shroud is unioned into the canopy. Its
  passage and leaf counterbore are cut through the same solid. The complete
  doorway is **1.02 × 1.94 m**, with a 100 mm floor threshold. The chamfered
  leaf is **1.096 × 1.978 m**, within the architecture door limits.
- The circular foundation is Boolean-notched before the shroud is joined;
  the vestibule supplies its own threshold, with no floor projecting through
  the lower doorway corners. A nominal 14 mm silicone joint follows the
  actual shroud/sphere cut across the top and both sides. Its matching pocket
  replaces structural volume, with no overlaid trim. It terminates at the
  foundation shoulder; there is no added bottom rubber strip. `M_Rubber`
  is nonmetallic, with roughness 0.85. A 0.1 mm retaining land prevents tangent
  Boolean surfaces at the original loft.
- Two three-knuckle hinges carry the leaf. Fixed bored sleeves are fused
  to the shroud, moving sleeves to the leaf. Retained stainless pins run
  through both stations with 1 mm radial and axial clearance. Welded necks
  connect the knuckles to their supporting solids.
- A square stainless shoot bolt has 75 mm guided travel. It retracts from
  the strike receiver before the leaf swings outward through 110°. Its
  integral 30 × 70 mm thumb grip sits inward from the free edge at z = 1.04 m,
  in a 140 × 100 mm operating pocket. The grip stays 2 mm behind the door
  face throughout its stroke; the pocket leaves 148 mm of leaf at the edge.
  The grip and bolt are Boolean-unioned, with no detached operating pieces. The
  free-side jamb has an integral blind strike hood, flush with the door face,
  concealing the bolt crossing without blocking its travel or the leaf swing. The
  annular rear gasket meets the closed leaf's rear seat. Leaf, seal, glazing,
  guide, receiver and pin volumes pass the sampled inter-part clearance audit.
- Construction unions remove internal mating walls. Hidden fastener faces
  and ground-contact faces are culled; glazing-visible interior is retained.

Skeleton: `Root` → `Door` → `Lock`, with rigid one-bone weights. `Door` rotates
about +Z at (0.590, −2.970, 0.430); the second coaxial hinge is at z = 1.820.
`Lock` slides along the leaf's +X. `_rig.json` records pivots, axes and limits.
`open` and `close` are non-looping, baked **2.4-second** clips at authored
30 fps (frames 0–72). Opening unlocks during frames 0–12, holds until 18,
then swings during 18–66. Closing reverses that order and engages only after
the leaf seats. The 1280 × 720 showcase demonstrates both clips at 30 fps.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.

## Regenerate

Run from `library/` with Blender 5.2:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/architecture/lunar_dome/model.py
& $blender --background --factory-startup --python models/architecture/lunar_dome/collision.py
& $blender --background --factory-startup --python models/architecture/lunar_dome/collision_check.py
& $blender --background --factory-startup --python models/architecture/lunar_dome/model.py -- --collision-exports-only
& $blender --background --factory-startup --python models/architecture/lunar_dome/validate.py
& $blender --background --factory-startup --python models/architecture/verify_dimensions.py -- --only lunar_dome
& $blender --background --factory-startup --python models/architecture/lunar_dome/scale_check.py
& $blender --background --factory-startup --python models/architecture/lunar_dome/preview.py
& $blender --background --factory-startup --python models/architecture/lunar_dome/inspection.py
& $blender --background --factory-startup --python models/architecture/lunar_dome/animate.py
```

The explicit collider export refresh retains the baked clips without FBX curve
simplification and exports shared, smooth collider corners without materials.
Scripts and documentation are the tracked source. Native models, rig metadata,
atlases, previews, QA reports and MP4 are generated/ignored outputs.
