# Grenade combustion atlas

Created with the built-in image-generation tool. The source PNG is delivered
pixel-for-pixel by `../export_fireball.py`.

Production prompt: create a square, truly transparent RGBA game VFX sprite atlas
with exactly four columns and four rows, sixteen chronological frames read
left-to-right, top-to-bottom. Frame one has a small white-yellow ignition at the
centre of dark grey dust. Frame two has a tiny orange flicker confined to the
central ten percent of the cloud's area. Frame three retains only one or two
dim ember flecks. Frames four through sixteen contain only neutral cool
charcoal/slate-grey regolith dust, without fire or orange/red/yellow glow.
Remove broad flames and glowing veins. Dust has no beige, cream, tan, brown or
sandy tint. Use a coherent expanding pressure/dust puff with detailed turbulent
volumetric billows and gradually dissipating wisps. No towering mushroom cloud,
lingering fuel fire, background, ground plane, cast shadow, text, grid lines or
checkerboard. Keep all sixteen cells nonempty.

Padding prompt: preserve that design and its exact 4-by-4 layout, scale and
recenter each complete sprite within the central 60% of its own cell, leaving
20% completely transparent padding on every side. No spark, glow, smoke or
detached pixel may touch any cell boundary. Scale whole sprites; do not crop.
