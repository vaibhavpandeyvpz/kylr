# Static industrial lights

assets: `batten_light/`, `sconce_light/`, `pole_light/`. The supplied
concept images guide their silhouette and finish; sizes are authored in metres
against Tensor's 1.753 m height. There are no actions, animated mechanisms or
game changes. Each prop uses a single rigid `Root` bone for existing library
export/collider compatibility.

| Prop | Authored size | Placement / projection |
| --- | --- | --- |
| Batten | 1.20 m long, 0.18 m casing width; 0.24 m across mounting saddles; 0.1025 m total drop | Origin at ceiling contact centre, z=0; diffuser faces -Z |
| Sconce | 0.43 m wide, 0.30 m high, 0.153 m wall projection including guard | Origin at wall contact centre, y=0; diffuser faces -Y |
| Pole | 4.189 m tall, 2.65 m crossarm span, 0.40 m square anchor footprint; six 0.32 × 0.26 m heads | Origin at floor flange centre, z=0; heads face forward and down with a small lateral spread |

## Construction and finish

`light_common.py` owns the fixture family. Each asset's `model.py` selects its
builder; the shared prop kit supplies exact booleans, rigid skinning,
connectivity and visibility culling. The casing is a lofted, machined casting,
with a removable bezel, recessed opal diffuser and a seated black gasket.
The exported `M_Light` is cool-white emission (strength 3); cyan status inlays
use `M_Emissive`. Structural surfaces retain the project's off-white
`M_Primary`, grey `M_Secondary`, matte-black `M_Frame` and stainless `M_Joint`.
All six used materials get unique, validated 2048 px painting atlases.

Batten mounting saddles have flat ceiling pads, bored anchor holes and socket
caps. The sconce has a wall backplate and a single fused guard, with four feet
seated on the bezel and an unobstructed centre projection line. The pole's
flange carries four anchors; four fused gussets brace its tapered mast. Integral
coupling shoulders, painted bands and three recessed status windows break up
the shaft. Its crossarm carries six fixed-aim U yokes, through-bored casting
trunnions, retained lock pins and fitted welded supports. A fused finned
heatsink seats against the back of each head. Hidden driver circuitry and
internal electrical feed through the mast/crossarm/supports are not modelled.
The yokes represent installation adjustments locked in the authored pose.

Manufactured components are closed and manifold before hidden-face culling.
An independent exact Boolean pair audit rejects overlapping solid interiors;
its 10 mm³ numerical tolerance accounts for sub-micron coplanar slivers in
Blender's world-space float calculations. Mating dimensions are shared, with
flush contact surfaces, genuine recesses and fish-mouth welded support seats.
Connectivity and coplanar-face checks are separate gates. Culled runtime
surfaces are intentionally open at sealed, never-visible interfaces.

## Projection contract

Batten and sconce export `LightProjection`; the pole exports
`LightProjection01` through `LightProjection06`. Their origins sit on the
diffuser surface. All are fixed under the prop rig. Metadata records their
Blender-space position, forward, up and suggested cone/range values. These are
placement suggestions, not a promise of scene illumination: emissive geometry
and projected runtime light are separate responsibilities.

The gizmo's authored Blender +Y points along the beam and +Z is its face up.
After glTF axis conversion, a Godot light child's **local -Z** points along the
beam and local +Y is up. `validate_lights.py` checks this directly in native GLB
node matrices as well as after GLB/FBX imports. No light nodes are exported.
Game assembly attaches lights to these frames and enables the
desired glow in the game environment; do not alter the mesh to aim the beam.

## Regeneration and validation

Run from `library/`, with Blender 5.2 at the path in `../docs/library/MODELLING.md`:

1. Run each `models/environments/<name>/model.py`.
2. Run each `preview.py` for the eight standard studio views.
3. Run each `collision.py` for separate convex collision exports and previews.
4. Run `models/environments/light_inspection.py` for square front-facing
   hero views, emission stills and a pole-head detail view.
5. Run `models/environments/validate_lights.py` for fresh GLB and FBX round trips.

The two shared inspection/validation scripts accept `-- <name>` to select one
asset. `model.py -- --draft` skips visibility culling and exports; it remains
subject to all mechanical checks and the triangle limit. No showcase or
animation script is needed for these static props.

Generated `.blend`, `.glb`, `.fbx`, `_rig.json`, UV guides and previews stay
ignored beside their generators. Do not copy them to `game/` until requested.
