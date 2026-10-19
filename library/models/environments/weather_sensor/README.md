# Weather sensor

Industrial weather station. Metres, floor-centred origin, front
−Y and up +Z. Height 2.5 m, compared with Tensor's authored 1.753 m.
The three ground pads and pinned diagonal braces support a sealed battery/data
logger enclosure and mast. The tripod remains locked in its working position.
Its tapered legs have bored shoulder/ankle eyes in machined clevises, retained
cross-pins and shoulder thrust washers. Brace eyes meet separate mast and leg
clevises. All pins share the exact bore axis; painted parts end at their seats.

Lofted shrouds use Tensor's off-white/grey paint, matte black framing,
stainless steel and green status inserts. Service inserts occupy Boolean
pockets; fastener heads seat on the covers. The rear enclosure has ventilation
cuts and a service-slack cable loop connected to the protected mast trunk.
The upper instruments comprise a GNSS radome, radiation-shielded temperature
probe, hollow three-cup anemometer, wind vane and offset-feed telemetry dish.
The dish faces forward with a modest upward angle; its integral rear boss ends
flush against a stub on a dedicated mast collar. The logger uses two flat
mounting pads. Crossarm beams end at mounting sockets and bolted pedestal
flanges. Radial locking screw heads sit on the real mast-collar facets; internal
threads are not modelled. Temperature-probe louvers have true open centre bores.

Root → Anemometer and Root → WindVane are rigid vertical-axis bearing joints.
`measure` loops for 4 s: two cup-rotor turns and ±25° vane response.
`gust` loops for 3 s: three rotor turns and ±45° vane response.
Keys are sampled every frame at 30 fps; both clips end on whole rotor turns.
There is no root motion. Tripod adjustments are locked, and the dish is fixed.

Run from `library/`, using the Blender 5.2 executable in `../docs/library/MODELLING.md`:

```powershell
& $blender --background --factory-startup --python models/environments/weather_sensor/model.py
& $blender --background --factory-startup --python models/environments/weather_sensor/preview.py
& $blender --background --factory-startup --python models/environments/weather_sensor/inspection.py
& $blender --background --factory-startup --python models/environments/weather_sensor/scale_preview.py
& $blender --background --factory-startup --python models/environments/weather_sensor/collision.py
& $blender --background --factory-startup --python models/environments/weather_sensor/collision_preview.py
& $blender --background --factory-startup --python models/environments/weather_sensor/validate.py
& $blender --background --factory-startup --python models/environments/weather_sensor/animate.py
```

Build checks closed manufactured solids, solid-volume overlap, connectivity,
every authored animation frame, full vane/rotor sweeps, coplanar faces and the
5,000-triangle render budget. Export preparation creates unique per-material
UV atlases. The standard collider builder exports convex companions under
500 triangles. Validation reimports GLB and FBX geometry, materials, scale,
rigid weights, clips and sampled animated transforms in fresh scenes.
Generated outputs remain ignored; no files are copied into `game/`.
