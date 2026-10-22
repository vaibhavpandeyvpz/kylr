# Combat material sources

Source PNGs are tracked editable inputs. Each has a Markdown prompt record in
`prompts/`, named after its source image. Keep generation or edit wording in that
record; generated texture manifests contain technical provenance and hashes.

| Source | Use | Prompt | Exporter |
| --- | --- | --- | --- |
| `rocket_cloud_height_source.png` | Spatial rocket combustion and grenade dust billows | [Prompt](prompts/rocket_cloud_height_source.md) | `export_rocket_cloud.py` |
| `muzzle_flow_source.png` | Directional flame filaments for muzzle and primary stream | [Prompt](prompts/muzzle_flow_source.md) | `export_muzzle_flow.py` |
| `fireball_flame_source.png` | Curling flare-cloud membranes and hot inner gas | [Prompt](prompts/fireball_flame_source.md) | `export_fireball_material.py` |
| `fireball_smoke_source.png` | Sparse cooling gas in fireball contacts | [Prompt](prompts/fireball_smoke_source.md) | `export_fireball_material.py` |
| `flak_dust_atlas.png` | Compact abrasion dust at flak contacts | [Retained edit prompt](prompts/flak_dust_atlas.md) | `export_flak_dust.py` |

Run exporters headlessly with Blender 5.2 from the library root. Packed material
maps contain linear albedo/height or density, matching normals and roughness.
Preserve independent RGBA channels with lossless imports, mipmaps, no alpha-border
repair and no premultiplication. The flak color atlas uses sRGB and normalized
quarter-cell UVs. Its exporter checks all sixteen frames for occupancy and clear
cell margins and copies the original pixels without resampling.
