# Raster area-light contribution check

`probe_area_light_zero_contribution.gd` creates an independent Forward+ scene
with three finite rectangle lights, opaque blockers, and receivers inside and
outside their support. It captures diffuse, metal, clearcoat, transmission, rim
and backlight, custom area-light code, and transparency as floating-point HDR.
A final control disables the lights while keeping the transparent material.
Hard shadow filtering and disabled temporal AA keep the comparison deterministic.

Run the script with reference and candidate editor binaries, a minimal Vulkan
Forward+ project, and a fresh absolute `--output=<directory>` after `--`.
Then run:

```
python misc/scripts/verify_area_light_zero_contribution.py <reference> <candidate> --output <fresh-report.json>
```

The verifier rejects incomplete captures, invalid dimensions, non-finite values,
or an ineffective lights-disabled control. It compares every HDR channel, reports
exact hashes, and allows at most 0.0005 absolute error. This checks appearance on
the fixture; measure rendering cost separately on real workloads.

The optimization rejects zero range attenuation only for built-in area shading.
It also skips fully shadowed built-in contributions when no transmission is
present. Custom area shaders retain their original calls and transmission retains
its independent shadow treatment. Range uses distance to the rectangle, not just
its center.
