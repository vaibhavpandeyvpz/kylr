# Lunar rover

Static six-wheel solar-rover scenery.
The overall deployed envelope is **3 m long × 2 m wide × 2.16 m high**.
Metres, front −Y, Z up, floor-centred origin. Six wheels meet the floor.  No animation actions are authored or exported.

## Construction

- The off-white chassis is a lofted unibody. Solar spars, instrument mounting
  pads, axle bearing seats and the science-arm seat are exact boolean unions
  with that shell. The small service lid sits in a machined recess.
- A bored transverse differential housing carries the suspension shaft.
  Each rocker and bogie is a single forged profile with actual pin bores.
  They occupy different axial lanes, with retained shafts and seated heads.
- Corner wheel carriers have integral motor housings, a flat support-boss
  seat, a blind support-pin bore and a coaxial axle bore. Steering stator
  caps stop on the upright tops and clear the inner wheel planes. The centre
  wheels use fixed carriers. Spacer sleeves support the offset bogie ends.
- Each metal wheel has a recessed hub, a returned bore wall and **24 integral
  axial grousers**. The hub shaft and its flanged retaining cap support the
  wheel; perimeter fasteners sit on its dish face.
- Six photovoltaic cartridges have recessed cell laminates and stainless
  perimeter frames. Cartridge seams remain separate from cell seams. The
  embedded 2048px material texture supplies clipped cell corners, two busbars
  per cell and fine conductor fingers. The solar surface is dark dielectric
  glazing (metallic 0, roughness 0.26, IOR 1.5, a light clear coat), rather than
  a mirror-metal plate. The cartridges terminate on the chassis spars.
- The stereo camera mast and dish bracket stand wholly on integral flat pads.
  The whip antenna stands on the central spar and clears the dish. The dish
  has a bored clevis, a bored cast tongue, a through-pin, retaining heads and
  captive thrust washers. Its tongue clears the clevis floor.
- The parked science arm has a bored shoulder clevis, retained elbow shaft
  with an axial spacer, and a bored wrist clevis integral to its tool case.
  Every arm eye is coaxial with its pin; the tool port ends on its case face.

The finish reuses the prop kit's `M_Primary`, `M_Secondary`, `M_Frame` and
`M_Joint`, with `M_Titanium`, `M_Solar` and `M_Optics` for rover surfaces.
There are no team colours or emissive structural materials.

## Regeneration and validation

Run from `library/`:

```powershell
$roverBlender = (Get-Command blender -ErrorAction Stop).Source
& $roverBlender --background --factory-startup --python models/environments/lunar_rover/model.py
& $roverBlender --background --factory-startup --python models/environments/lunar_rover/validate.py
& $roverBlender --background --factory-startup --python models/environments/lunar_rover/preview.py
& $roverBlender --background --factory-startup --python models/environments/lunar_rover/inspection.py
```

`model.py` uses the shared item-table modelling kit without changing its
source. It checks part connectivity, mechanical seats and clearances, exact
bounds, and coplanar overlaps before and after assembled visibility culling.
It retains natural Body, Suspension and Wheels meshes on a fixed Root bone;
each must meet the owning modelling guide's **5,000 triangles per exported
mesh** cap. Counts and mechanical fits are recorded in `_rig.json`.

Native material atlases are uniquely packed at 2048px and checked for UV
overlap. The cell grid and tread finish are baked onto those UVs and embedded
in GLB/FBX. The two surface PNGs and all other build outputs are generated.
The `.blend`, exports, metadata, UV guides and previews remain ignored files.

`validate.py` imports each export into a fresh scene and checks exact bounds,
mesh counts, triangle budgets, materials, readable embedded images, unit
scale, normalized rigid Root weights, finite UVs inside 0..1 and no actions.
`preview.py` is the unchanged generic studio renderer. `inspection.py` adds
an elevated hero view and six close-ups of the suspension, wheel mount, cell
sectioning, solar supports, instruments and science arm.

`-- --draft` saves a connected, coplanar-audited, unculled build without
delivery exports. No showcase animation is needed for this static asset.
