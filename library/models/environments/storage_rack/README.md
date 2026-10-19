# Storage rack

Static industrial workshop prop, authored only in the asset library. Front and
bin access face **−Y**, up is +Z, origin is the centre of its floor footprint.
Overall dimensions are **1.49 × 0.69 × 1.90 m**, including the feet. Tensor is
1.753 m tall; shelves stand at 0.36, 0.97 and 1.58 m. No animations are authored.
The fixed Root bone keeps the asset compatible with the prop/export pipeline.

The asset has the three-tier silhouette, paired picking bins,
grated decks and braced end frames. Native Tensor off-white and grey paint,
matte black and stainless steel provide the finish. The rack has four 80 mm sealed box-section uprights, lofted
load-spreading floor shoes with two seated anchor sockets each, integral pierced
X-web end castings, top ties, and three continuous lofted shelf shrouds. Their
ends meet the posts on square flats. The shelf walls receive twelve removable
punched-steel grate cassettes on welded seating sills. Recessed wear strips and
upright panels terminate flush with their seat surfaces.

Four one-piece picking bins have 14 mm soles, side/rear walls and sloped front
mouths, with flush label inserts. Soles bear on the deck centre spine; they do
not sink into the surrounding shroud. A continuous three-turn stored cable
rests on the top deck, with ferrules sharing its exact end cross sections. It
is loose stored stock, not live wiring; no disconnected hanging cable is used.

`model.py` shares the existing `light_common.py` and item-table manufacturing
framework. Before culling it verifies closed manufactured solids, tests every
candidate pair with an exact intersection-volume audit, and follows a surface
contact graph from a foot through all 77 parts. The surface-contact check also
samples edge interiors to verify broad bin soles resting across narrow deck
spines. No assertion or collision tolerance is relaxed to conceal geometry
errors. Only mutually hidden mating faces and invisible undersides are culled.
Unique per-material painting UVs use the existing 2048 px atlas workflow.

Run from `library/`:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/environments/storage_rack/model.py
& $blender --background --factory-startup --python models/environments/storage_rack/preview.py
& $blender --background --factory-startup --python models/environments/storage_rack/inspection.py
& $blender --background --factory-startup --python models/environments/storage_rack/collision.py
```

`-- --draft` builds an unculled inspection scene without replacing the runtime
exports and without enforcing the final triangle budget. Rebuild normally
after using it. `preview.py` is the unchanged generic studio renderer;
`inspection.py` adds a three-quarter hero and an actual Tensor scale view.
`collision.py` is the unchanged generic prop collider generator. Generated
Blender scenes, GLB/FBX exports, rig metadata, atlases and images stay ignored.
