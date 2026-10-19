# Bunker

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Walkable architecture, front −Y, up +Z, origin at ground centre.
Authored to fit a 10 × 10 m placement area,
including the regolith apron, approach and full door swing.
The building is offset 0.30 m toward +Y within that placement square to keep
the entire outward door sweep inside its front edge. The generator checks all
animation frames and an independent 3° hinge sweep against the square.

## Construction

The asset uses a squat
octagonal tapered shell, a dark glazed upper band, pale sloped armour, cyan
service lights, recessed entry and irregular regolith footing. The studio
camera uses mild telephoto compression and an elevated front three-quarter
view with a near-white sweep. Materials use the existing props' off-white and
grey paints, matte black and stainless steel, plus dark pressure glazing and
lunar dust. The interior is fully traversable.
`M_Glass` is black with 0.10 alpha (10% opaque), independently of the armour.

Budget: 5,000 rendered triangles in total. Unique per-material 2048 px painting
atlases. Scripted exact booleans and lofts; GLB primary, FBX fallback. Static
utilities have no gratuitous motion; action clips are `open` and `close`.

## Mechanical interfaces

- Shell: 6.6 m base width; height approximately 3.142 m. Integrated pressure
  walls, ceiling, deck and entrance vestibule. Recessed wall cells share an
  integral machined perimeter frame, with no overlaid or peeking rib ends.
- Passage: 1.35 m wide, 2.056 m high, 0.110 m threshold reached by a ramp.
  Chamfered doorway corners reduce clearance locally; central Tensor-sized
  traversal volume is unobstructed.
- Door: rigid `Door` hinge about a vertical axis, 105° outward travel. Three
  bored interleaved knuckles with retained pins, 3 mm radial bearing clearance,
  and a coaxial geared motor anchored to the stationary jamb.
- Locks: `TopBolt` and `BottomBolt`, 90 mm opposed retraction. Frames 0–15
  unlock; the door stays shut until frame 21, then swings until frame 81.
  `close` reverses the sequence, seating the leaf before extending the bolts.
- Both clips: 96-frame duration at 30 fps, in place, non-looping.
- Fixed conduits use bored saddle clamps. Fairings, roof hatch and light
  status bezels seat on structural surfaces. Glazing and emissive inserts fill real
  machined openings. Terrain has a central hole and an open entry approach.
- The tapered removable cassettes use a constant 105 mm parallel-edge rim,
  including their chamfers; their recessed faces and bolt lands derive from
  the same tapered outline.
- There is no interior light mesh. `BattenLightMount`, parented to `Root`, is
  at Blender (0, 0.30, 3.20) m with the building's axes. Place the separate
  batten light at that mount in the game later. Both export formats preserve it.
- Dust microrelief is procedural in Blender previews; GLB uses constant PBR
  dust values. `SK_ArchitectureRegolith` uses only `M_Regolith`; UV0 `TiledSurface`
  maps Blender XY at one repeat per 2 m and UV1 `MaterialAtlas` is its unique
  painting layout. The terrain node can take the world's crater material
  independently. Game material work is deferred.

## Build and verification

Run from `library/` with Blender 5.2 as documented in `../docs/library/MODELLING.md`:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/architecture/bunker/model.py
& $blender --background --factory-startup --python models/architecture/bunker/preview.py
& $blender --background --factory-startup --python models/architecture/bunker/inspection.py
& $blender --background --factory-startup --python models/architecture/bunker/collision.py
& $blender --background --factory-startup --python models/architecture/bunker/animate.py
& $blender --background --factory-startup --python models/architecture/bunker/scale_check.py
```

`model.py` rejects disconnected manufactured parts, solid intersections,
animation clashes, coplanar surface overlaps and budget overruns. Interior
faces are retained; ground-contact undersides and internal mating faces are
culled. Collision uses separate convex architectural slabs and a moving door
leaf, preserving the room and entry void. There is no gameplay trigger.
The 316-triangle architectural collider intentionally omits terrain dressing
and small service fittings. It is a room/door blocking companion, not a final
