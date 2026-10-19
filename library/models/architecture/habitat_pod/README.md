# Habitat pod

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Jump-access habitat, authored in metres, front **-Y**, up **+Z**,
origin on the ground at the footprint centre. The asset has the compact
faceted pressure shell, single hinged hatch, pinned landing gear and exterior
thermal hardware. Finishes follow Tensor and the existing industrial props:
off-white and grey paint, matte black, stainless steel and cyan access status.

The body is 3.50 m wide and 3.35 m deep. The cabin is raised 0.20 m in authoring
coordinates, keeping its original internal dimensions. Each landing foot is
0.20 m closer to the centre, for a 3.78 m total stance. Tensor is 1.753 m
tall. The delivered deck is **about 0.746 m above ground**;
the entrance is **1.20 × 2.11 m**, with clipped corners. The hollow cabin has
a flat walkable floor and a 2.399 m central standing height. There is no ramp.
Windows are black with **0.10 alpha**. Interior lighting is represented only
by `InteriorCeilingLight` and `InteriorRearLight` gizmos. `PlayerMount` marks
the cabin deck. These are exported bone-parented empties, not light meshes.

The primary volume is one hollow lofted pressure casting with an integral deck
and matching chamfered window cutouts and bezels. Machined inserts have shared mating dimensions;
supports seat against the actual casting rather than buried overlapping boxes.
Two widely spaced interleaved bored hinge assemblies carry the pressure door. Retained
through pins use a bore sized for full rotational clearance of the polygonal
pin, including intermediate angles. A captive powered header bolt withdraws
100 mm before the door rotates outward 105 degrees. Its cylinder and header
receiver have fitted mounting saddles and real bores. Power/control routing
is enclosed in the hinge and door casting; no exposed cable crosses the hinge.

Four tapered landing members have integral bored eyes between casting clevis
cheeks and ground-pad forks, with through-milled lightening bays and fitted
running clearances (1 mm at the body forks and 2 mm at the pad forks).
Each upper flange is wholly on the planar belly, centred at X ±0.88 m,
Y ±0.70 m, clear of the shell chamfers and expansion grooves.
A second off-axis locking pin positively arrests
each upper pivot; the landing members cannot fold under load. The stationary
landing assembly has no artificial deploy animation. Two front single-acting
hydraulic braces sit alongside the load rails; the rear pair are fixed struts.
Their cylinder and rod ends
have integral bored eyes captured in pinned forks; gland collars meet exposed
stainless rods. A charge hose connects each barrel coupling to a belly union,
with the supply manifold enclosed in the pressure casting. The landing locks
carry the parked load; these braces are rigid Root geometry, not independent
telescoping controls. The rear thermal cassette
has geometric cooling slots, flanged fasteners and stainless return pipes
terminated on bulkhead gland faces.
Mirrored side processors and the crown air-treatment module have bolted
flanged castings, removable bezels and integral geometric metal fins. Formed
coolant loops have tangent-radius bends, hex unions and bored standoff clamps.
Separate black power loops terminate in strain-relief and bulkhead glands.
The door reinforcement has horizontal pressed ribs and captive fasteners;
the vertical ribs are omitted at the user's request. Its chamfered recess
follows the plate outline with a 5 mm clearance at its straight edges.

Rigid skeleton: `Root → Door → Lock`; exactly one influence per vertex.
Event clips `open` and `close` each span 96 frames at 30 fps (3.2 seconds).
Opening releases the bolt, then moves the door. Closing reverses that order.
There is no continuous idle motion. `animate.py` renders the complete sequence
with held endpoints using the same studio as the other props.

`model.py` checks manifold manufactured parts, exact resting solid intersection
volumes, connectivity, every animation frame, a one-degree door sweep and
coplanar faces. The configured render budget is **7,500 triangles total**. Visibility
culling temporarily separates the transparent window panes, so glass cannot
hide cabin faces. Their closed thickness is retained and the glazing is
rejoined before material UV atlases and export. `collision_extras.py` preserves the cabin
and doorway using convex wall bands and a separate moving leaf; small hardware
is omitted. The 488-triangle structural proxy includes the deck, pressure shell,
landing members, ground pads and moving door. Exterior thermal hardware, pipes,
handles and hinge projections are not covered by this proxy; these require a
collision policy review before game integration. `validate.py` freshly imports GLB and FBX to verify bounds, scale,
triangles, materials, UVs, rigid weights, skeleton and sampled clip transforms.

Run from `library/` using Blender 5.2 headless:

```powershell
$blender = (Get-Command blender -ErrorAction Stop).Source
& $blender --background --factory-startup --python models/architecture/habitat_pod/model.py
& $blender --background --factory-startup --python models/architecture/habitat_pod/preview.py
& $blender --background --factory-startup --python models/architecture/habitat_pod/scale_preview.py
& $blender --background --factory-startup --python models/architecture/habitat_pod/inspection.py
& $blender --background --factory-startup --python models/architecture/habitat_pod/collision.py
& $blender --background --factory-startup --python models/architecture/habitat_pod/model.py -- --collision-exports-only
& $blender --background --factory-startup --python models/architecture/habitat_pod/validate.py
& $blender --background --factory-startup --python models/architecture/habitat_pod/animate.py
```

Generated blends, runtime exports, atlases, reports, previews and videos are
ignored build outputs. The Python files remain the editable source.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.
