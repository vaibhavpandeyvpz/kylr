# Combat effect building blocks

The reusable kit contains twelve rigid meshes totalling 3,286 triangles: smooth and
lobed shells, an open tapered nozzle, an annular pressure front, an axial card,
an asymmetric lofted flame envelope, twisted vortex membranes, a metal chip,
a compact packet shell, two lightning ribbons and induction filaments. Game-owned shaders/controllers
compose these into layered effects with independent timing, palette and budgets.

All meshes use one rigid Root bone, have no collision, and place their origin at
the emitter or volume center. Analytic UV0 supports scrolling density and material
masks. Budget: 5,000 triangles for the complete kit, 1,500 per mesh.

Run from the library root using Blender 5.2 LTS:

```powershell
& $Blender --background --factory-startup --python models/effects/combat_effects/model.py
& $Blender --background --factory-startup --python models/effects/combat_effects/model.py -- --roundtrip
```

The generator validates geometry and weights and exports GLB, FBX, a native Blend
and rig metadata. Fresh GLB/FBX round trips verify mesh inventory, triangle counts,
Root weights and metre bounds. Copy validated runtime GLB, rig JSON and textures
to `game/assets/models/effects/combat_effects/`; library outputs remain ignored.

Procedural data textures are a 256-square tileable four-channel turbulence field
and a 512-square gas atlas used by muzzle crowns. Bitmap material sources and one
Markdown prompt record per image live under [source/](source/README.md). Material
exporters produce linear packed maps for rocket/grenade gas, muzzle/stream flame,
and fireball flare clouds. The dedicated flak abrasion atlas remains a color
flipbook. Export metadata records source hashes and independent channel samples.

The kit has no fluid simulation. Runtime gas uses closed spatial integration
volumes and curling textured membranes; decorative particles are bounded.
Generated captures and editable showcase scenes belong in ignored build/reports
folders. Do not import third-party meshes, textures, scenes or shader code into
these generators.
