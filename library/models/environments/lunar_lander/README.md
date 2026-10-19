# Lunar lander

Static environment prop for placement near an arena. Library asset only: no
game import, placement, runtime data or game code is included in this change.

The footprint is exactly **5 × 5 m**, including the four landing pads; overall
height is **5 m**, including the antenna. Origin is the ground-plane centre,
front is −Y and Blender +Z is up. All geometry is in metres. One fixed `Root`
bone preserves compatibility with the prop pipeline. There are no actions.

  Lofted,
faceted shrouds use native KYLR off-white/grey paint, matte black, stainless
steel, titanium and bronze. Dark opaque glazing is the only added material.
There are no national markings, foil textures or crew interior.

## Manufactured interfaces

- The descent shell has an actual internal cavity and boolean service openings.
  Its clevises and drag-stay bosses are fused into the shell. The grey bands are
  material regions of its surface, rather than overlapping cover rings.
- Capsule tanks have machined neck sockets, seated bottom pedestals, roof
  connections and retaining bands. Their volume clears the chassis walls.
- The cabin meets the descent stage on a common plane. The airlock's flat
  fairing is fused into the cabin, giving its wide door a planar seat. The jamb,
  door and compressed gasket occupy distinct depths. Alternating hinge
  knuckles have bores, jamb mounts and a separate stepped door leaf.
- The three pressure windows fit wholly within one shoulder slope. The
  annular bezels are flush with that surface; glazing is recessed 3 mm.
  Flank radiators and the rear service cover fit inside pockets on single flats.
- Each landing strut has a bored upper eye inside the chassis fork, with
  1 mm side clearances and a through-pin whose head and nut seat on the cheeks.
  Its narrowed neck terminates entirely within the eye's solid rim. The sleeve
  has an open shaft bore and a shouldered bronze gland; the shaft has about
  4 mm minimum radial clearance and overlaps only inside the sleeve.
- Each pad carries a bored fork on its flat top. The main strut eye and both
  drag-stay eyes occupy separate axial lanes on the foot pin, with 1 mm gaps.
  Drag stays connect to bored chassis lugs. The tapered shaft neck and stay
  ends terminate inside the solid rims of their eyes, clear of the pin bores.
- The thrust deck, injector flange, chamber, bell and exit lip meet at common
  planes. The bell has an open bore and return wall. The parked engine has no
  exhaust effect.
- The hatch tread is supported by welded triangular gussets. Bent grab rails
  have mounting feet on the tread and jamb. Rungs terminate within the ladder
  rails. Both ladder shoes meet z = 0; their rails end in blind sockets.
- Antenna bases fit on the flat crown. A fixed cast carrier meets the dish's
  planar rear mounting flange. Feed-strut ends are clipped to the reflector's
  actual facets. RCS units have bases seated wholly on cabin flats; their
  outlets begin on the unit's end faces. The status lamp has a lens pocket.

## Regenerate

Run from `library/` with the repository's Blender 5.2 executable:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/environments/lunar_lander/model.py
& $blender --background --factory-startup --python models/environments/lunar_lander/validate.py
& $blender --background --factory-startup --python models/environments/lunar_lander/preview.py
& $blender --background --factory-startup --python models/environments/lunar_lander/inspection.py
```

`model.py` uses the shared item-table kit without modifying its source. It checks
mechanical fits, connected parts, bounds and coplanar overlap, culls unseen faces
across the complete assembled prop, and packs unique 2048px native material
atlases. Body and landing gear are retained as separate rigid meshes on the
same fixed skeleton. Each is checked against the guide's **5,000 triangles per
exported mesh** limit; the combined count is recorded separately in `_rig.json`.

`preview.py` is the unchanged generic renderer and produces eight studio views.
`inspection.py` adds close-ups of upper and foot joints, pin heads, the hatch,
ladder shoes and antenna. Neither renderer saves the Blender scene. The local
coplanar audit uses a common projection axis for both faces in a candidate pair,
avoiding false overlap reports between distant, symmetric diagonal surfaces.

`-- --draft` makes a checked, unculled `_draft.blend` for quick inspection;
it does not produce delivery exports. Full builds generate `.blend`, `.glb`,
`.fbx`, `_rig.json`, UV masks and guides. All are ignored build outputs.
No `animate.py` is needed for this explicitly static asset.

For the later game handoff, `collision.py` provides the shared convex-fitting
pipeline, with a static-rig fallback and no animation export when there are
no actions. Run it after the final model build, inspect its outputs, then
perform the game import and verification.
