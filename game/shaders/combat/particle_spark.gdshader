shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never;
uniform vec4 tint : source_color = vec4(1.0, 0.85, 0.4, 1.0);
varying float life;
void vertex() { life = INSTANCE_CUSTOM.y; }
void fragment() {
	float fade = 1.0 - smoothstep(0.2, 1.0, life);
	float tip = smoothstep(0.0, 0.12, UV.y) * (1.0 - smoothstep(0.75, 1.0, UV.y));
	ALBEDO = mix(tint.rgb, vec3(1.0), 0.45);
	EMISSION = tint.rgb * 5.0 * fade;
	ALPHA = tip * fade;
}
