"""Start the standard adaptive collider pass at its measured budget tolerance.

The station's first 10 mm pass produced 2,240 triangles; the earlier silhouette
needed 51.6 mm decomposition tolerance to fit under 500. Starting there avoids
repeating the same failed finer passes. The shared engine still reports actual
coverage/protrusion and coarsens further only if required by the triangle cap.
The render geometry and mechanical seat tolerances are unchanged.
"""
ALLOWANCE = .1032
TRI_MAX = 500
