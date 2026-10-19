# Beacon lantern

Static industrial beacon, **1.00 m high**, **0.78 m maximum head diameter**,
with a **0.46 m base** and **0.36 m service pedestal**. Tensor is 1.753 m tall.
Metres; floor-centre origin at z=0; service/front faces Blender **−Y**, up **+Z**.
There are no actions or animated mechanisms.

The asset has the broad lantern head, domed weather cap, protective
straps, cyan equatorial diffuser and narrow off-white pedestal. Native KYLR
off-white/grey paint, matte-black seals and stainless hardware match the
existing props. The opal light band and two inset driver indicators use the
same cyan emission as the existing industrial lights.

The pedestal has three lofted cassettes with turned ends, retained by the end
collars. The broad front service cover has four captive screws; each rear
cassette has one central retainer. A sealed driver chassis runs to the head.
The light engine seats the guard at both ends. Each basket is one exact-boolean
union of sixteen swept straps and two annular mounting rails, with no buried
overlapping solids left in the delivery. The diffuser has separate upper and
lower compression seals and fits exactly between its rails. The removable
domed cap sits on its own seal and has four flush recessed socket screws on
its planar flange. Thread forms, internal electronics and wiring are omitted.
The ground flange is a freestanding foot; its broad solid base provides ballast.

`model.py` is the editable source and reuses the existing industrial light kit.
Build from `library/` using the Blender 5.2 executable in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/environments/beacon_lantern/model.py
& $blender --background --factory-startup --python models/environments/beacon_lantern/preview.py
& $blender --background --factory-startup --python models/environments/beacon_lantern/scale_preview.py
& $blender --background --factory-startup --python models/environments/beacon_lantern/collision.py
& $blender --background --factory-startup --python models/environments/beacon_lantern/validate.py
```

`preview.py` and `collision.py` are the existing model-agnostic tools.
`scale_preview.py` loads Tensor's authored body and default head at original scale.
All rendered geometry is rigidly weighted to one fixed Root bone. `-- --draft`
skips the complete visibility pass, UV preparation and runtime exports; draft
geometry is not a delivery and can exceed the final triangle budget.

Each manufactured part must be closed and manifold before the shared exact
solid-volume audit and connectivity check. The overlap audit rejects volumes
above its 10 mm³ numerical tolerance. The complete build removes unseen faces,
rejects coplanar overlap, enforces the 5,000-triangle cap and generates five
unique, non-overlapping 2048px native material UV atlases.

The static collision companion uses three coaxial convex pieces. It preserves
the pedestal/head neck and domed silhouette, conservatively filling the small
guard apertures and fastener sockets. Coverage checks use rendered vertices
and triangle centroids; it has no trigger. `validate.py` checks both render and
collision GLB/FBX in factory scenes: bounds, triangle counts, unit mesh scale,
normalized rigid skin weights, Root bone, material names, UV bounds and no actions.
Generated exports, previews, UV guides and reports stay ignored by Git.
