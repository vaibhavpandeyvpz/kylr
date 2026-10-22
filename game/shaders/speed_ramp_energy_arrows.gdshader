shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled, blend_add, depth_draw_never;

uniform vec4 tint : source_color = vec4(0.35, 0.95, 1.0, 0.7);
uniform float phase_offset = 0.0;
uniform float motion_speed = 1.0;
varying float phase;

void vertex() {
	phase = fract(TIME * motion_speed * 0.8 + phase_offset + 0.05);
	// Four 0.30 m chevrons: 0.35 m pitch leaves a 0.05 m clear gap.
	VERTEX.z += phase * 1.4;
}

void fragment() {
	ALBEDO = tint.rgb;
	EMISSION = tint.rgb * 1.4;
	ALPHA = tint.a * smoothstep(0.0,0.12,phase) * (1.0-smoothstep(0.75,1.0,phase));
}
