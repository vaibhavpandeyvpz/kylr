# Combustion and dust texture sources

The PNG atlases in this folder are editable source assets and stay in Git.
They contain 4 × 4 frames with transparent margins around each sprite:

- `fireball_atlas.png`: projected flamethrower flame/fume particles.
- `flak_dust_atlas.png`: dedicated compact abrasion dust used by flak contacts.
- `fire_contact_atlas.png`: surface fuel flame and dissipating wisps.

`export_fireball.py` validates alpha, frame occupancy and tile edges, records
content hashes and copies pixels without resampling. Shader sampling uses
normalized quarter-cell coordinates. Preserve RGBA values and transparent
margins; runtime alpha rejection suppresses low-opacity fringe pixels.

`rocket_cloud_height_source.png` is a continuous grayscale billow material for
spatial rocket gas and grenade dust. Its [authoring prompt](rocket_cloud_prompt.md) describes the
built-in image generation. `export_rocket_cloud.py` derives matching linear
albedo/height and normal/roughness maps and records channel samples and hashes.
These packed maps contain material data in alpha and require lossless import,
mipmaps, and disabled alpha-border repair and premultiplication.
