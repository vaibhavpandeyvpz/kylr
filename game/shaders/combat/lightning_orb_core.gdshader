// Adapted from KYLR: Galaxy rebound_orb_core; Arena lightning palette.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque, shadows_disabled;

uniform vec4 core_color : source_color = vec4(0.002, 0.008, 0.018, 1.0);
uniform vec4 ember_color : source_color = vec4(0.455, 0.749, 1.0, 1.0);
uniform float emission_energy : hint_range(0.0, 16.0) = 5.0;
uniform float animation_speed : hint_range(0.0, 10.0) = 1.0;
uniform float deformation : hint_range(0.0, 0.1) = 0.018;
instance uniform float phase = 0.0;

varying vec3 local_position;

float distortion_field(vec3 point, float time) {
	float broad = sin(point.x * 31.0 + time * 1.7 + phase);
	broad += sin(point.y * 37.0 - time * 2.1 + phase * 1.7);
	broad += sin(point.z * 29.0 + time * 1.3 - phase * 0.8);
	float crossflow = sin((point.x + point.z) * 53.0 - time * 2.8);
	return broad * 0.24 + crossflow * 0.18;
}

void vertex() {
	float time = TIME * animation_speed;
	float field = distortion_field(VERTEX, time);
	VERTEX += NORMAL * field * deformation;
	local_position = VERTEX;
}

void fragment() {
	float time = TIME * animation_speed;
	float field = distortion_field(local_position, time);
	float fractures = abs(sin(
		local_position.x * 61.0
		+ sin(local_position.y * 47.0 - time * 1.9) * 2.7
		+ sin(local_position.z * 53.0 + time * 1.4) * 2.1
	));
	float ember_veins = smoothstep(0.965, 0.997, fractures + field * 0.055);
	float facing = abs(dot(normalize(NORMAL), normalize(VIEW)));
	float rim = pow(1.0 - facing, 2.15);
	vec3 tint = mix(core_color.rgb, ember_color.rgb, ember_veins * 0.46 + rim * 0.022);
	ALBEDO = tint;
	EMISSION = ember_color.rgb * emission_energy * (ember_veins * 0.18 + rim * 0.018);
}
