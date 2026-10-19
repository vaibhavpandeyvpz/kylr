// Compact confined plasma packet; no smoke, fireball or solid cylinder.
shader_type spatial;
render_mode unshaded, blend_add, cull_back, depth_draw_never;
instance uniform float core_layer = 0.0;
void fragment() {
	float facing = clamp(abs(dot(normalize(NORMAL),normalize(VIEW))),0.0,1.0);
	float rim = pow(1.0-facing,1.8);
	float phase = UV.y*TAU*3.0-TIME*9.0;
	float wave = 0.5+0.5*sin(phase);
	float width = max(fwidth(wave),0.06);
	float band = smoothstep(0.8-width,0.8+width,wave);
	vec3 tint = mix(vec3(0.02,0.64,0.85),vec3(0.82,0.96,1.0),core_layer);
	ALBEDO = tint;
	EMISSION = tint*mix(1.2,2.8,core_layer);
	ALPHA = mix((0.12+rim*0.28+band*0.12)*smoothstep(0.0,0.2,facing),pow(facing,0.4)*0.85,core_layer);
}
