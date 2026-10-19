# Library guidelines

Asset-generator commands run from `library/`; Git commands run from the repository
root. Read the [modelling contract](../library/MODELLING.md) before asset work.
Python generators are the editable source. Regenerate and validate native exports
before copying runtime assets into `game/`.

## Authoring and validation

- Use Blender 5.2 headless with `--background --factory-startup --python`.
  Helpers outside Blender use `library/.venv/Scripts/python.exe`.
- Use metres and the asset's documented axes, origin and attachment frames.
  Apply transforms; keep rigs, joints, gizmos, animation and collision companions
  consistent. Mechanical parts use connected solids and rigid skinning.
- Preserve authored flat PBR paint/metal finishes, glass and emission.
  Canonical regolith and screen textures retain their runtime UV coordinates.
- Validate collision and motion through every sampled pose, inspect previews,
  and perform GLB/FBX round trips. Geometry changes rebuild colliders.
  Skeleton or attachment changes require dependent animation regeneration.
- Single door openings are at most 1.5 × 2.1 m; double openings normally span
  2.0 × 2.1 m. Interior floor-to-ceiling clearance is at most 3.0 m.
  Validate actual walkable surfaces, door travel and Tensor clearance.
- Generate assets from their own scripts. Runtime inclusion is defined by the
  game catalogs and handoff tooling, not by the presence of a library export.
- Keep generated meshes, rig JSON, previews, animation targets and reports out
  of Git unless a documented source-asset exception applies.

## Geometry budgets

Default props and weapons use 5,000 render triangles; detachable ammunition
uses 1,500 and weapon projectiles use 500. Character render meshes use 15,000.
Generators and validators enforce these asset-specific totals:

| Asset | Render triangles |
| --- | ---: |
| Item cradle | 5,500 |
| Habitat pod | 7,500 |
| Flak cannon | 7,500 |
| Pulse gun | 7,500 |
| Bastion, hangar, lodge and hub | 10,000 each |
| Cistern | 12,000 |
| Laboratory | 15,000 |

Architecture retains a 5,000-triangle per-mesh ceiling. Use the generator's
budget and exported metadata for delivered totals.

## Map assembly

Map-owned geometry comprises integral platform/bridge castings and machined
openings. Separate props, architecture, lights and lunar scenery retain their
own budgets and native gizmo transforms. Report these counts separately.
Skyfall's map-owned budget is 75,388 triangles; other maps default to 25,000.

Recessed fixtures require their native footprint plus 1 mm clearance per side
in both render and collision cuts. Cutters extend 0.5 m above the surface and
through the required pit depth. Do not move or scale props to hide overlaps.

`pillar_platform` sits below the pillar; sample the native ram extension to meet
the next floor underside. Raised weapon fixtures use `weapon_holder_wall` and
its `WeaponHolderMount`. Placement metadata, visual openings, colliders and
traversal must agree.
