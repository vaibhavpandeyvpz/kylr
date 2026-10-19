# Stasis chamber

Gameplay prop with a rigid opening door. The native scene, render exports and collider companion carry `open` and `close` clips.

The asset uses the chamfered vertical pressure enclosure,
cyan window, dark condenser crown, pedestal cabinet and restrained metal
service details. Project finishes remain clean, matching Tensor and the other
industrial props, with clean paint and metal finishes.

## Scale and placement

The ground footprint is exactly **1.5 m length (Y) × 1.25 m width (X)** in
the closed rest pose, established by the foundation flange. The opening door
has a separate swept clearance outside that resting footprint.

- Metres; floor-centred origin at z = 0; viewing panel faces Blender −Y.
  Standard GLB export maps this to Godot +Z, with +Y up.
- Overall envelope, including service lines and flange: **1.250 × 1.500 ×
  2.679 m** (width × depth × height).
- Interior standing floor: **0.530 m**. Interior ceiling: **2.330 m**.
  A nominal 1.753 m Tensor has 47 mm of vertical headroom.
- The interior is 820 mm wide; its depth accommodates Tensor's feet and rear
  pack. The idle fit uses the actual generated Tensor and all authored idle
  frames at `(0, 0.02, 0.53)`, with no chamber intersection and at least
  **16.9 mm** above-ankle clearance. Floor contact is tested separately.

## Construction

The enclosure is a continuous lofted pressure casting with a machined cavity
and an 80 mm rear wall. The door bezel seats against its front perimeter;
14 mm cyan glazing at 18% opacity seats inside a continuous black gasket.
Two coaxial hinges at z = 0.80 and 2.06 m carry the complete door, its gasket, glazing, pull handles, latches and status strip. The vertical axis is `(0.55, -0.65, 1.43)` in Blender metres, ahead of and outside the fixed pressure frame. Machined stationary bearing brackets seat against the shell; retained pins pass through their bores and the moving knuckles. Welded moving leaves connect the knuckles to the bezel, with axial and radial running clearance. The door opens outward 120 degrees, fully clearing the occupant opening. `open` and `close` each take 1.5 seconds at 30 fps, with eased motion and fixed hinge position. A limited `Door` bone supports manual posing.

The foundation flange supports the equipment cabinet and chamber sill.
Recessed removable hatches give service access; the side grilles represent
equipment cooling plenums. A thermal backplate carries upper and lower
manifolds, connected return tubes, bored retaining saddles and sensor rails.
Interior wash lights sit in sidewall channels behind the occupant's arms.
The crown carries a ventilation grille and two connected condenser bridges.
Exterior service loops have both ends seated on their side cassettes; door
pull handles terminate on the bezel. No unsupported ornamental machinery is
added. Stasis itself is fictional; the housing and service routing have
manufacturing and maintenance logic.

## Regeneration

Run from `library/`, with Blender 5.2 as specified in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/gameplay/stasis_chamber/model.py
& $blender --background --factory-startup --python models/gameplay/stasis_chamber/preview.py
& $blender --background --factory-startup --python models/gameplay/stasis_chamber/inspection.py
& $blender --background --factory-startup --python models/gameplay/stasis_chamber/collision.py
& $blender --background --factory-startup --python models/gameplay/stasis_chamber/validate.py
& $blender --background --factory-startup --python models/gameplay/stasis_chamber/animate.py
```

`model.py` reuses the library's static industrial solid helpers and generic
prop framework. It builds all editable geometry from code. `inspection.py`
requires Tensor's generated scene and the retargeted idle blend; it renders
three-quarter, scale-comparison and occupied views, then records the fit.
The comparison-only character and its animation are never saved or exported
with this asset. `.blend`, GLB/FBX, reports, UV guides and previews are
ignored generated outputs.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.
