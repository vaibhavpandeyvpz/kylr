# Bastion

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Duplex sci-fi bastion. The editable source is `model.py`; Blender,
GLB, FBX, rig metadata, previews and videos are generated outputs.
Metres, front -Y, up +Z, origin at grade below the centre.

The asset uses the compact chamfered pressure hull, front-and-side panoramic
observation belts with diagonal braces and a solid rear machinery bulkhead, plain off-white lower walls, heavy
corner ribs, pale waist bands and stepped roof crown. Its roof has two forward
signal/pressure pods, a directly roof-seated central telemetry enclosure, three flanged rear
return headers, a large rear extraction bonnet.
Seated crown grille blades, radial bonnet
stiffeners and paired telemetry lens ports form the roof layout.
Retained flange studs seat on the roof pipe terminal flanges.
Materials use KYLR off-white M_Primary, grey M_Secondary, matte black M_Frame,
stainless M_Joint and cyan M_Emissive. M_Glass is black, nonmetallic glazing at 0.10 opacity, as requested.
Pressure-wall surrounds use one off-white finish; no triangle-centre or
position-based black patches are assigned around window or wall-panel edges. The openings pass
through the real pressure shell; the interior remains walkable.
An exposed metallic foundation ring supports the building.
Eight exterior sconce gizmos seat directly on the lower pressure walls, with
two fixtures per face. The lower walls have no armor cassettes, status bars or
cassette studs.

The long central plinth is removed. The front side pods and central white
controller share y = -5.1875 m at their front edges. Their two side margins and
two inter-part gaps are all 1.1125 m across the 12.6 m roof. The rear header
skid and round extraction bonnet share y = +5.1875 m at their back edges,
with the same 1.1125 m rear and outer-side margins. These dimensions are
calculated from the footprints and checked against actual source vertices.
The controller's optical bezel and lenses are recessed within its footprint.
The roof signal wire and its end fittings are removed as requested.

Placement is within 15 x 15 m, excluding optional regolith. The ground floor is
at 0.2553 m, upper floor at 3.4468 m. The 13 x 13 m upper deck leaves 150.069 m2
usable after chamfered corners and the rear cargo opening. Upper headroom is
at least 2.1223 m. The entrance is 1.50 m wide with 2.10 m central headroom;
its integral approach has no step at the doorway.

## Mechanical assembly

A single inward-opening pressure leaf turns 105 degrees on three retained,
interleaved bored hinge sets and a coaxial sealed geared drive. This is an
original Bastion stainless steel door, with a full-height recessed stainless steel armor insert, vertical
glove-clear pull and a small flush status lens. There are no paired white
Laboratory door plates. Its 1.95 m approach serves the 1.5 m clear opening.
The hinge forks and drive flange lie entirely on flat interior jamb lands,
clear of the collar chamfers. Double-precision barycentric checks prove every
mounting corner lies on an actual host triangle within 10 microns. The moving
eyes use bores sized for full rotary clearance around the faceted retained pin;
1 mm axial clearance separates the fork cheeks and moving knuckle. The upper
shoot bolt retracts 120 mm before the door swings. All parts use rigid weights.
Crown fitting backs have a 2 micron assembly tolerance at their seating planes.

The flat open cargo platform is 3 x 3 m towards the rear, traveling 3.1915 m between
floors. Integral rear crosshead, two fixed guide rails with C-shaped shoes,
and two fixed shafts with powered nut carriages carry its load. Guide feet
seat at the foundation; upper brackets seat against the uninterrupted 200 mm
rear metal bulkhead. There are no rear windows or window frames. Every corner
of the two guide and two shaft top mounting footprints is checked against
the actual inner wall triangles at y = 6.50 m.
A 20 mm running gap surrounds the deck aperture. Side landing guards leave
the front loading lane clear. There are no floating or telescoping stages.

Four event clips at 30 fps, frames 0-96: open, close, lift_up, lift_down.
The rig is Root / Door / Lock / CargoLift. No continuous idle motion is needed.

The collision companion exports structural convex pieces and articulated
entrance/lift blockers, plus SK_BastionLiftPlatformTrigger, a distinct
12-triangle occupancy area weighted to CargoLift. It sits 16 cm above the deck
and is inset 2 cm from its edges. Treat it as an area, separately from blockers.

SK_ArchitectureRegolith / M_Regolith is the common optional perimeter node,
rigidly weighted to Root and excluded from collision. It can be hidden without
changing the building. Its triangles count toward the 10,000 total ceiling;
its bounds may extend beyond the building's placement envelope. Eight interior
fixture placement gizmos seat on real surfaces; no runtime lamps are included.

## Regeneration

From library/, use Blender 5.2 as specified in AGENTS.md with
--background --factory-startup --python-exit-code 1 --python, in this order:

1. models/architecture/bastion/model.py
2. models/architecture/bastion/collision.py
3. models/architecture/bastion/validate.py
4. models/architecture/bastion/preview.py
5. models/architecture/bastion/inspection.py
6. models/architecture/bastion/scale_check.py
7. models/architecture/bastion/animate.py

Source checks enforce solid intersections, manifold manufactured parts,
connectivity, full animation-frame clearance, coplanar surfaces, 15 m placement,
10K total and 5K per render mesh. Native GLB/FBX round trips verify materials,
unique UVs, dimensions, rigid weights, clips and sampled skin transforms.
Tensor idle/walk/run geometry is checked through the open doorway in both
directions, plus standing clearance across both storeys and lift landings.
Inspection and showcase cutaways exist only in temporary render copies.
