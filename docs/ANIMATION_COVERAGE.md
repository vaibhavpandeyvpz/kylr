# Character animation coverage

The game imports the 408 Tensor clips listed in `assets/animations/manifest.json`. The character animation selector and match presentation assign 408 of them to gameplay. `tests/test_character_animation_coverage.gd` checks that each assigned clip exists in the imported catalogue and reports any unassigned clip.

| Clip group | Use |
|---|---|
| Idle and aim | Weapon-specific standing and crouched idle, aimed variants, pistol kneeling idle after a sustained stationary crouch, and seven additive vertical aim poses. |
| Movement | Eight directions of walk, run, sprint and crouch walk. Pistol walk/run arcs respond to turning while moving forward or backward. |
| Transitions and actions | Pistol stand/kneel transitions; standing/crouched left/right turns; takeoff, airborne, falling and landing; fire, reload and nonlethal hit reaction. |
| Death and results | Front, back, right and headshot death variants; procedural `death_explode` for rocket, grenade and EMP kills; defeated pose; all 13 victory dances selected across match results. |

Scoped rifle headshots are identified by a ray hit on the equipped Tensor head collision mesh (`SK_TensorHead*Col`). Body collision hits remain ordinary hits. This keeps the damage rule tied to the animated collision rig rather than a world-height estimate.

Aim overlays store and restore only bones with changed components. Hip compensation
composes the parent rest/pose chain locally before the final skeleton update,
so collision attachments receive the completed pose once. Recoil, hit reactions
and the authored pitch samples remain live on every physics tick.
