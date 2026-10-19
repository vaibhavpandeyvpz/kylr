# Terminal

Static floor-standing industrial operator terminal, authored in metres by
`model.py` with Blender 5.2. Front is **-Y**, up is +Z, origin at floor centre.
Static asset without animation clips.

The full bounds are **0.72 × 0.678 × 1.85 m**. The 0.62 m control shelf has
sealed buttons at **1.089 m**, a booted joystick and a rotary selector. The
inclined display centre is **1.35 m** high and tilts 15 degrees upward toward
its operator. `terminal_scale.png` compares it with the actual 1.753 m Tensor.

The structural chain is anchor flange → lofted equipment cabinet → control
shelf → fused spine/hood → spine flange → twin fitted welded gussets → inclined
VESA flange → monitor shell. The VESA screws have a **100 × 100 mm** pattern.
Its flange shares the exact monitor back plane; gusset ends are trimmed to the
flanges. Mounts do not project through the housing or terminate in air.

The spine and overhead hood are one Boolean-unioned lofted shell. Hatches,
upper spine armour, cooling cartridges, diagnostic port and controls sit on matching
flats or machined seats. The warm task lamp sits flush in the hood's angled
front lip. Native off-white/grey paint, matte black, stainless steel and restrained
bronze follow the other props. Surfaces use clean paint and metal finishes.

The **14 mm diameter** rear power/data cable uses tangent circular bends and
parallel-transported constant-radius sections. Both ends meet compression glands
normally, and two bored clamps retain the straight run. The shared helper in
`../roof_display_assembly/model.py` also supplies roof displays and workstation
cables. It checks section radius, tangent orthogonality and bend clearance.

`SK_TerminalScreenMain` uses `M_Screen` with original embedded telemetry, analytic
UV0 and a painting atlas on UV1. Its surface replaces the backer's face to avoid
z-fighting. `SK_TerminalGlass` is a 2 mm blue pane at 10% opacity with a 10 mm
LCD air gap. All visual vertices have one fixed Root influence. Screen and
pane share the housing collider instead of adding duplicate flat hulls.

Run from `library/` using the Blender executable in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/environments/terminal/model.py
& $blender --background --factory-startup --python models/environments/terminal/preview.py
& $blender --background --factory-startup --python models/environments/terminal/inspection.py
& $blender --background --factory-startup --python models/environments/terminal/collision.py
```

The generator reuses the workstation's monitor builder and generic prop framework.
`-- --draft` skips final visibility culling, atlases and exports while retaining
solid-volume and connectivity checks. Generated files remain ignored.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.
