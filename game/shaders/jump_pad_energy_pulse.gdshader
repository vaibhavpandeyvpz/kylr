shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;

uniform vec4 tint : source_color = vec4(0.55, 1.0, 0.78, 0.48);
uniform float phase_offset = 0.0;
uniform float rise_height = 0.65;
uniform float rise_speed = 1.4;
uniform float motion_speed = 1.0;
varying float phase;

void vertex() {
	phase = fract(TIME * motion_speed * rise_speed / rise_height + phase_offset + 0.15);
	VERTEX.y += 0.025 + phase * rise_height;
}

void fragment() {
	vec2 p = abs(UV - vec2(0.5));
	float edge_distance = abs(max(p.x, p.y) - 0.46);
	float band = 1.0 - smoothstep(0.012, 0.022, edge_distance);
	ALBEDO = tint.rgb;
	EMISSION = tint.rgb * 1.8;
	ALPHA = band * tint.a * sin(phase * 3.14159265);
}
