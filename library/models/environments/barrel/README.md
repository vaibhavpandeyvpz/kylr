# Barrel

Static industrial service reservoir, **0.95 m tall**, nominally **0.60 m across**.
Authored in metres, origin at floor centre, service/front towards Blender -Y,
up +Z. Tensor is 1.753 m tall. No electronic screen, animation or game integration.

Two broad off-white stamped half-shells sit over a sealed drum. Their turned-in
shoulders fit into grey end collars; shallow formed beads stiffen the shells.
The front has one fused matte-black instrumentation casting with a genuine flat
mounting surface. It supports an analogue pressure gauge (physical spindle,
needle, graduations and a gasketed glass lens) and a capped drain valve with a
pinned shutoff lever and a two-ended impact guard. A single capped charge socket
sits completely on a flat of the right-hand cassette. Stainless hardware uses
the existing KYLR material palette; the gauge lens uses a transparent PBR slot.

The removable top cover is gasketed, with a retained fill plug, a front toggle
lever pinned through bored clevis cheeks, and a rear retention cleat. Its two
side lifting slots preserve a continuous cast rail. The top handle has two broad
feet on the lid and a joined bridge. The model depicts a closed static assembly;
no actions, contents, pressure rating, explosive behaviour or hidden plumbing
are specified. Fastener heads have machining clearance in their blind seats;
unseen internal threads are omitted. The armour layout follows the front service
casting, rear retention and formed sheet construction.

Build from `library/`, using the Blender 5.2 executable in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/environments/barrel/model.py
& $blender --background --factory-startup --python models/environments/barrel/preview.py
& $blender --background --factory-startup --python models/environments/barrel/scale_preview.py
& $blender --background --factory-startup --python models/environments/barrel/collision.py
```

`preview.py` and `collision.py` are the existing model-agnostic tools.
`scale_preview.py` reads Tensor's authored default body/head without modifying it.
The single fixed Root bone supports the existing pipeline; no actions are exported.
Generated exports, UV guides, collision source data and reports stay ignored.

Manufactured parts must be manifold, connected, and free of solid overlap before
hidden mating surfaces are culled. The exact overlap audit uses a 10 mm³ numerical
threshold. The transparent gauge lens is excluded from opaque occlusion testing,
then restored; its dial and needle remain visible. Visible coplanar overlap,
the 5,000 triangle limit, the 1 m maximum envelope and UV non-overlap are checked.
Each of the five used materials gets its own unique 2048px UV atlas.

The static collision proxy retains the top dish and covers all rendered vertices
and triangle centroids within 0.1 mm. Small hardware recesses, guard spaces and
rim bevels are simplified to fit the 500-triangle cap, with up to 30 mm conservative
overcoverage. It contains no triggers.
