# Lunar shelter

The [shared architecture dimensions contract](../README.md#door-and-interior-dimensions)
owns current door and inside-height limits. Delivered dimensions and mechanical
travel are recorded in the regenerated `_rig.json`. Run `../verify_dimensions.py` after rebuilding.

Architectural cover, facing −Y, origin centred on the ground.
The shelter has open front, left and right approaches and a solid service wall
at the rear. The 4.60 × 4.60 m chamfered foundation includes integral ramps up to a 0.12 m
deck. The complete building, optional apron and 95° service-hatch swing stay
within the requested 5 × 5 m square. The canopy is 3.08 m high, with captive
roof screw heads reaching 3.088 m. The clear front lane is 2.80 m wide; side
lanes have at least 2.40 m usable width and 2.38 m headroom.

The canopy, inclined arms and rear piers use one continuous external profile,
avoiding exposed arm tips at separately chamfered roof corners. Roof skins,
front armour, rear-pier access covers and hatch face plates have machined seats.
Each side retains only its top machined access plate; the inclined side faces
remain bare, with no white or black perimeter ribbon. The exterior amber
controller has a vertical face and a centred indicator, with a rear wedge
fish-mouthed to the canopy. All visible heads use consistent square-drive
socket recesses in retained hex caps.

The rear service hatch has two interleaved bored hinge forks, integral moving
knuckles, through-pins and retaining caps. Axial reveals and polygonal-bore
radial clearance allow its full 95° swing. Copper power and stainless coolant
conduits are supported by bored glands seated on the back wall.

The circulating rotors belong to sealed coolant cartridges feeding the canopy
heat-spreader circuit, rather than air fans on the lunar surface. Each rotor
has three integral vanes and a retained motor shaft, with a protected sealed
black sight glass at **10% opacity**. Hidden internal plumbing is represented
by the sealed wall terminations, rather than spending the budget on enclosed
pipework.

`SK_Shelter` and `SK_ArchitectureRegolith` total **4,178 triangles**, including
the apron’s 96 triangles. `M_Regolith` and rigid `Root` weights match the other
architectural props. The apron can be hidden independently and has no blocking
collision. The collision companion has 260 triangles in convex pieces and
preserves the three approaches and service opening.

`Root` owns the structure; `ServiceHatch` owns the rear leaf;
`CoolantRotorLeft` and `CoolantRotorRight` own the pump impellers. `circulate`
is a 4-second whole-turn loop at 30 fps. `service_open` and `service_close`
are 2.4-second event clips. Every part is rigidly weighted to one bone.

The roof underside has exactly one `BattenLightMount`, and the inside back wall
has exactly one `SconceLightMount`. Their transforms are ray-fitted to the actual
structural surfaces and exported on `Root`. There are no interior light meshes
or actual light objects in the delivery. Exterior status inserts use emissive
materials independently of these future fixtures.

Run from `library/` using Blender 5.2:

```powershell
$shelterBlender = (Get-Command blender -ErrorAction Stop).Source
& $shelterBlender --background --factory-startup --python models/architecture/shelter/model.py
& $shelterBlender --background --factory-startup --python models/architecture/shelter/preview.py
& $shelterBlender --background --factory-startup --python models/architecture/shelter/inspection.py
& $shelterBlender --background --factory-startup --python models/architecture/shelter/collision.py -- --no-render
& $shelterBlender --background --factory-startup --python models/architecture/shelter/validate.py
& $shelterBlender --background --factory-startup --python models/architecture/shelter/scale_check.py
& $shelterBlender --background --factory-startup --python models/architecture/shelter/animate.py
```

The build rejects solid overlap, disconnected parts, moving collisions, excess
triangles, coplanar duplicate surfaces and any 5 m motion-envelope violation.
Native render and collision GLB/FBX round trips check dimensions, materials,
rigid weights, actions and every sampled animation matrix. Scale verification
uses actual Tensor idle/walk/run samples and the standing capsule through all
three approaches, in both directions, against both render and collision meshes.
This is library geometry verification; engine physics and lighting will be
tested during a separately requested game handoff.

Generated blends, native exports, rig data, UV guides, images, videos and reports
are build outputs. The Python generators and this document are editable sources.
