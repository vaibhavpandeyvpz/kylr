# Lodge

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Lunar architecture, authored entirely by `model.py` in headless
Blender 5.2. Metres, front -Y, up +Z, origin at grade centre. The fixed
foundation is exactly 15 x 15 m; equipment height is approximately 3.564 m.

## Construction

  The user requested removal of the front/rear
gussets and their fasteners in the final design. The material palette follows KYLR's existing
props: off-white `M_Primary`, grey `M_Secondary`, matte-black `M_Frame`,
stainless `M_Joint` and cyan `M_Emissive`. Black `M_Glass` has 0.10 opacity.
The lower interior wall finish is assigned by inward-facing surfaces rather
than triangle centroid height, preventing diagonal grey wedges. Floor and
pressure ceiling retain their continuous grey finishes.

A continuous machined skirt and pressure shell stand on a 100 mm deck.
Both approach ramps are carved into that deck, with no raised sill. The roof
has a continuous 3.10 m soffit, lofted shoulder, perimeter compression eave
and upper coaming. Its centre is a continuous deck: the central plate and all
slope ribs were removed at the user's request. Four thermal/power cassettes
stand on separate bolted flanges; the shrouds have recessed intake cartridges,
supported louvres, flush top grilles and pocketed cyan status lenses.
Service conduits terminate at glands and use bored guide collars on fully
seated pedestal feet. No loose wire crosses a moving door.

Equipment flange bolts use 105 mm corner offsets. Their complete 21 mm head
radii fit between the flange and pod chamfers, with a checked minimum 5 mm
edge allowance. Hinge foot checks sample 72 points over the actual flat jamb
and door lands. Exact solid-volume intersections, rigid-part connectivity,
all action frames and one-degree door sweeps are checked before export.
Moving parts retain faceted bearing clearances and 0.2 mm seating allowances.

Three window bays per side each contain two 1.30 m wide through-openings with
continuous gaskets. Each 3.78 m clear bay has equal 393.33 mm gaps at both
edges and between the pair. Structural mullions carry visible end fasteners. The front and rear
walls are clean continuous pressure-shell surfaces.

## Traversal and rig

Front and rear entrances are each 1.5 m wide x 2.088 m high. Their 600 mm ramps
rise 77.32 mm to the floor. Interior headroom is at most 3.0 m. Each door uses three
interleaved bored hinges, retained through-pins, a coaxial geared drive and an
enclosed captive shoot bolt. The bolt retracts 135 mm before a 110-degree
outward swing; closing seats the door before extending the bolt. Reserve
approximately 2 m approach space beyond each foundation edge for the sweep.

Rigid weights are 1.0 to one of Root, Door, Lock, RearDoor and RearLock.
`open_front` / `close_front` and `open_rear` / `close_rear` are independent
96-frame event actions at 30 fps, containing only that door and lock's tracks.
`open` / `close` are front aliases; `open_both` / `close_both` control both.
Stationary utilities have no invented idle motion. Door geometry and export
helpers reuse the proven cistern cartridge through a separate imported module;
editing this lodge does not change cistern's generator or outputs.

Four `BattenLightMount*` and two `SconceLightMount*` attachment gizmos seat on
actual interior surfaces, with local +Z facing into the room. There are no
interior fixture meshes or lights in the runtime asset.

## Optional lunar surface

`SK_ArchitectureRegolith`, material `M_Regolith`, is a separate optional mesh
weighted to Root. Hide or remove it independently. It has no collider and
is excluded from the 15 x 15 m building placement bounds. Its irregular outer
edge extends beyond the foundation, while both entrance approaches are flat.
Its 84 triangles count toward the render budget, following the shared
[architecture contract](../README.md).

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.
