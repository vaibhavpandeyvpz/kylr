shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never;
uniform float opacity : hint_range(0.0, 1.0) = 1.0;
void fragment() {
	float rim = pow(1.0 - abs(dot(normalize(NORMAL), normalize(VIEW))), 2.2);
	float filaments = pow(0.5 + 0.5 * sin(UV.x * 65.0 + sin(UV.y * 35.0 + TIME * 13.0) * 2.0 - TIME * 18.0), 12.0);
	vec3 blue = vec3(0.16, 0.5, 1.0);
	ALBEDO = blue;
	EMISSION = mix(blue, vec3(0.85, 0.95, 1.0), filaments) * (rim + filaments) * 2.0;
	ALPHA = (0.2 + rim * 0.5 + filaments * 0.3) * opacity;
}
