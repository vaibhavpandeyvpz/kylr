# Pillar Platform

A reversible **1 × 1 × 1 m** container-style structural platform. Its source
is `../mechanical_mounts.py`; the profile follows `container/model.py`.
The top and bottom are solid load plates. Four framed side windows contain
real **8 mm folded sheets**, with six container-style corrugations per face.
The fold relief is 25 mm and remains recessed behind the structural posts.

The continuous frame has stepped end rails, formed transitions, chamfered
corners and three-face lifting pockets at all eight corners. The material
assignment follows the container's native palette: **M_Secondary grey frame and solid end plates**
and **M_Primary off-white corrugated sheets**. Material roles
are assigned to complete structural surfaces, preserving uniform boundaries.

Origin is the block centre, with exact bounds ±0.5 m on each axis.
`PillarMountTop` at Z +0.5 faces up; `PillarMountBottom` at Z −0.5 faces down.
Both accept the separate native pillar with an identity local transform.
Top/bottom geometry is symmetric. Pillars are imported only for previews.

Collision uses ten simple convex pieces for the load plates, corner posts
and closed side panels, leaving the central hollow empty. Small corner
pockets and corrugation valleys are simplified for blocking collision.
Render geometry totals 2,084 triangles; collision totals 120 triangles.
The platform is static, rigidly weighted to Root, with no animation clips.

Run from library using the Blender 5.2 executable specified in AGENTS.md:

```powershell
& $blender --background --factory-startup --python models/architecture/pillar_platform/model.py
& $blender --background --factory-startup --python models/architecture/pillar_platform/collision.py
& $blender --background --factory-startup --python models/architecture/pillar_platform/validate.py
& $blender --background --factory-startup --python models/architecture/pillar_platform/preview.py
```

Map integration uses native geometry/collision without scaling. Gizmo-only map
previews omit this prop; populated previews and runtime import it. Its triangles
are excluded from the map-owned casting budget.
