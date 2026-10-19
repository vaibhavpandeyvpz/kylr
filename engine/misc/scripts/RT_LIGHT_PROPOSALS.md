# Bounded light-proposal experiment

`GODOT_RT_LIGHT_PROPOSALS=1` requests up to sixteen independent light proposals
per stochastic lighting evaluation when the uploaded set contains more than
sixteen lights. Smaller sets retain enumeration. It is disabled by default.
The existing uploaded-light limit is unchanged; this does not remove lights,
shadows, geometry, samples per pixel or path bounces.

The host constructs an allocation-free alias table using a mixture of 90%
estimated power and 10% uniform probability. Area-emitter power includes its
rectangle area. The uniform component retains support even for a zero power
estimate. All-zero estimates use uniform sampling. Invalid table input falls
back to enumeration. The table occupies previously unused words in the existing
112-byte light record; the resource layout and buffer size remain unchanged.

For each proposed light, the reservoir weight is `target / source_pdf`. Final
shading multiplies the selected contribution by
`sum(weights) / (proposal_count * selected_target)`. Zero-contribution proposals
still count toward the proposal count. This is initial resampling only, with no
reuse between pixels or frames. It is informed by the general sampling approach
described in the [RTXDI integration guide](https://github.com/NVIDIA-RTX/RTXDI/blob/main/Doc/Integration.md);
it does not integrate or claim to implement RTXDI/ReSTIR's complete pipeline.

The PDF is reconstructed from the stored FP32 alias table, rather than from its
unrounded requested distribution. The shader receives that realized PDF for
compensation. GPU arithmetic remains finite precision. Selection variance can
increase relative to full enumeration; transport correctness alone is not image
quality or performance qualification.

`probe_rt_light_alias.cpp` exercises the actual host helper. Build it as a
standalone C++17 executable, then run `verify_rt_light_alias.py --probe ...
--output ...`. The independent oracle integrates the stored buckets, checks
full support and PDF normalization, estimates resampling energy with a separate
inverse-CDF selection implementation, and rejects an incorrect normalization.
Invalid inputs must leave the output untouched.

Neither numerical fixture accepts moving image quality, real-scene performance,
release packaging or unsupported-platform behavior. Those remain separate gates.
