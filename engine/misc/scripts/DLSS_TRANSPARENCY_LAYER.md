# Retired separate transparency-layer prototype

Removed from the renderer after the experiment failed broader image review.
The environment variable below no longer enables a rendering path. This page
records the historical design and evidence; its commands are not current usage.

`GODOT_DLSS_RR_TRANSPARENCY_LAYER=1` enables an experimental single-view,
non-MSAA ray-traced path. It is off by default and is not production-qualified.

The ordinary raster overlay still writes the original color framebuffer.
Two additional RGBA32F attachments capture an affine representation in the same
draws: `composited = color + transmittance * opaque`. Color starts at zero;
transmittance starts at one. Color uses the original material blending.
Transmittance multiplies by one minus source alpha for mix/premultiplied alpha,
stays unchanged for add/subtract, multiplies by source RGB for multiply, and
becomes zero for an opaque particle. RGB opacity is then one minus transmittance.
Reconstruction receives the untouched opaque input plus the separate color and
RGB-opacity SDK tags. It does not denoise a color that already includes the layer.

The main framebuffer, ordinary depth testing, particle simulation, draw ordering,
lights and shaders are retained. Separate capture adds attachment bandwidth and
an opacity conversion; it does not replay all geometry. This is not an FPS claim.

Run the temporal fixture with `--transparency-layer --capture-inputs
--resolution 1920x1080`. In addition to its existing controls, actual sampled
color/transmittance must recompose the ordinary pre-reconstruction framebuffer
within 0.002 RGB, and converted opacity must match within 0.00001. This sample
check is deliberately limited: it does not certify every pixel or blend mode.

Before enabling by default, validate overlapping and occluded layers, negative
subtractive color, HDR multiply factors outside the usual opacity range, shader
screen/depth reads, fog, viewport resize, mode changes and resource release.
Post-transparent compositor writes are not captured in the extra attachments;
applications that modify color there need explicit handling or fallback.
Frame generation and multiview are also outside this prototype's qualification.
Production SDK acceptance of a texture is not proof of correct composition.

The first v678 attempt failed render-graph validation because the opaque input
was declared twice as a graph dependency. A shared input/guide now contributes
one dependency while retaining both SDK tags. The failed run remains evidence
of an implementation error, not a quality result.

After that fix, v680 passes the existing full-HD percentile trail test, its
raster and submitted-ghost controls, guide tolerances, and sampled composition
checks without validation or exit-leak errors. Maximum sampled composition error
is 0.000312. This is a narrow pass: the maximum-pixel metric still detects a
one-column edge displacement on three jitter phases. Turning sharpening off in
v681 does not remove it. The layer remains opt-in while alignment is investigated;
a percentile pass does not establish production image quality.

v683 captures all 40 application-effects cases at fixed simulation rate and
particle seeds with native RR evaluation, synchronization validation and clean
exit. Explosion shape is retained, but visual comparison shows more jagged fine
edges. This is capture/correctness evidence, not adoption or performance approval.

v685 records the native input coverage as well as output coordinates. At step
zero, the captured opaque particle spans input columns 270..371, while output red
coverage spans 537..740 at 2x scaling. The predicted output bounds are 541..742.
Other phases show smaller horizontal offsets, and vertical coverage stays close
to the predicted bounds. The discrepancy is not resolved by disabling sharpening.
No arbitrary pixel offset or wider exclusion guard has been introduced to hide it.
Opaque particle material/depth/motion-guide capture should also be evaluated before
choosing a production approach; those particles currently share background guides.
