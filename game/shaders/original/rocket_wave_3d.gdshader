shader_type spatial;
render_mode unshaded, blend_mix, cull_back, depth_draw_never;
uniform float effect_opacity = 1.0;
instance uniform float progress = 0.0;
void fragment() {
	float rim = pow(1.0-abs(dot(normalize(NORMAL),normalize(VIEW))),5.0);
	float envelope = smoothstep(0.0,0.015,progress)*(1.0-smoothstep(0.025,0.12,progress));
	ALBEDO = vec3(0.65,0.69,0.73);
	EMISSION = vec3(0.15,0.11,0.07)*envelope;
	ALPHA = rim*envelope*effect_opacity*0.06;
}
