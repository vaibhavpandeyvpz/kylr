// Independently authored tiny casing chips with brief residual incandescence.
shader_type spatial;
render_mode blend_mix, depth_draw_never;
varying float fragment_age;
void vertex() { fragment_age = INSTANCE_CUSTOM.y; }
void fragment() {
	ALBEDO = vec3(0.17,0.15,0.13);
	METALLIC = 0.65;
	ROUGHNESS = 0.75;
	EMISSION = vec3(1.0,0.48,0.14)*pow(1.0-fragment_age,4.0)*1.5;
	ALPHA = 1.0-smoothstep(0.7,1.0,fragment_age);
}
