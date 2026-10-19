# Combat effect building blocks

Production brief: preserve the currently selected KYLR effects' visual roles,
silhouettes, palettes, sizes and timing, using independently authored resources.
Rendered captures belong to the consuming game's ignored reports, never to this
library's redistributable source. Do not import, trace, copy or decimate vendor
meshes, textures, scene files or shader code into these generators.

## Delivery contract

- Build with Blender 5.2 LTS, headless, from the library root:
  `blender.exe --background --factory-startup --python models/effects/combat_effects/model.py`.
- The reusable kit contains a smooth shell, lobed burst shell, open tapered
  nozzle, annular pressure front, axial gas card and two electrical ribbons,
  plus an asymmetric lofted flame envelope, four twisted vortex membranes and
  a three-dimensional fan of tapered burst streaks, a thick asymmetric metal
  chip, a compact packet shell and thin induction filaments. The 13 meshes total
  3,414 triangles. The complete effect uses
  independent hot/cooling/smoke/pressure/filament layers; a bare sphere or card
  is not a finished replacement.
  Budget: at most 5,000 triangles for the whole kit and at most 1,500 per mesh.
- All meshes use one rigid Root bone. These are visual-only effects without
  collision or mechanics. Their origin is the emitter/volume center rather than
  floor contact. Analytic UV0 is preserved for scrolling noise and masks; it is
  intentionally not repacked as a painted surface atlas.
- GLB and FBX are generated, with rig metadata, procedural PNG textures and
  texture provenance/hashes. Generated outputs remain ignored in the library;
  validated runtime files are copied to the game.
- Data textures: one 256-square four-channel tileable turbulence field and
  512-square independent gas/smoke atlases. Deterministic seeds and formulas are
  the editable source. Masks are linear data, not sRGB color.
- Color flipbooks: three original transparent 4x4 atlases for rocket combustion,
  grenade detonation dust and a spreading fuel flare. These were created with
  OpenAI Imagegen without third-party image inputs. Retained editable sources and
  prompt records live in `source/`; run `export_fireball.py` to validate alpha,
  cell occupancy and margins, then export unchanged pixels with hashes. Their
  1,254-square dimensions use normalized quarter-cell UVs. Color is sRGB.
- The kit is not a complete effect. Game-owned shaders and controllers provide
  the independently tuned layering, palette, animation and preset budgets.

## Verification

Regenerate from `model.py`, run the asset validators and collision checks,
perform fresh GLB/FBX round trips, and inspect the native previews.
The generated rig metadata records delivered dimensions, budgets,
materials, attachment frames and animation clips.
