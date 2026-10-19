# Spatio acoustic propagation

Spatio is the collision-based propagation layer inside the Godot audio director.
The director owns cue priority, voice pooling, travel delay, mix buses and
`AudioStreamPlayer3D` playback. The local robot's `AudioListener3D` supplies the
ear position and aim orientation.

## Propagation

- Three direct paths sample obstruction from the listener's ears to each world
  emitter. Paths end 25 cm before the emitter to avoid the contact surface.
- A collision body's `spatio_material` metadata selects low- and high-frequency
  transmission. Collider names infer concrete, metal, glass, grate or fabric;
  explicit metadata overrides that inference.
- The per-voice low band controls level. The high/low ratio controls a low-pass
  filter. Both bands blend over time as cover moves.
- The director budgets 15 rays per 50 ms tick and samples voices round-robin.
  Local sounds and sources too close to need obstruction checks are skipped.
- Godot 3D audio supplies positional panning. Map zones supply shared reverb.

## Verification

Tests cover free paths, solid obstruction, material changes, open cover, voice
budgets and cue pools. Combat diagnostics expose voice, ray and mixer-peak
metrics. Audition left/right, front/back and vertical sources, moving cover and
wall openings on headphones and speakers.
