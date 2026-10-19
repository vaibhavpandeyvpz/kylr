// Adapted from KYLR: Galaxy ion_charge_shell; Arena lightning palette.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add, shadows_disabled;

uniform vec4 primary_color : source_color = vec4(0.455, 0.749, 1.0, 1.0);
uniform vec4 secondary_color : source_color = vec4(0.741, 0.937, 1.0, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.025, 0.1, 0.28, 1.0);
uniform float emission_energy : hint_range(0.0, 12.0) = 4.5;
uniform float animation_speed : hint_range(0.0, 10.0) = 1.0;
uniform vec2 noise_scale = vec2(4.0, 2.0);
uniform vec2 noise_scroll = vec2(0.3, -0.2);
uniform float deformation : hint_range(0.0, 0.5) = 0.12;
uniform float shell_opacity : hint_range(0.0, 1.0) = 0.36;
uniform float edge_power : hint_range(0.25, 8.0) = 2.0;

instance uniform float phase = 0.0;

varying vec3 local_position;
varying float surface_noise;

float wave_noise(vec3 position, float time) {
	float broad = sin(position.y * noise_scale.y * 5.1 + time * noise_scroll.y * 4.0);
	float around = sin(atan(position.z, position.x) * noise_scale.x + time * noise_scroll.x * 5.0);
	float detail = sin(dot(position, vec3(8.7, 13.1, 6.3)) - time * 2.7);
	return broad * 0.48 + around * 0.34 + detail * 0.18;
}

void vertex() {
	float time = TIME * animation_speed + phase;
	float radial_length = max(length(VERTEX.xz), 0.001);
	vec2 radial = VERTEX.xz / radial_length;
	surface_noise = wave_noise(VERTEX, time);
	VERTEX.xz += radial * radial_length * surface_noise * deformation;
	local_position = VERTEX;
}

void fragment() {
	float time = TIME * animation_speed + phase;
	float noise = wave_noise(local_position, time);
	float facing = abs(dot(normalize(NORMAL), normalize(VIEW)));
	float rim = pow(1.0 - facing, edge_power);
	float current = smoothstep(0.1, 0.88, sin(local_position.y * 31.0 - time * 8.0 + noise * 4.0) * 0.5 + 0.5);
	float energy = clamp(rim * 0.78 + abs(noise) * 0.34 + current * 0.28, 0.0, 1.0);
	vec3 tint = mix(tertiary_color.rgb, primary_color.rgb, smoothstep(0.05, 0.72, energy));
	tint = mix(tint, secondary_color.rgb, current * rim * 0.5);
	ALBEDO = tint;
	EMISSION = tint * emission_energy * (0.45 + energy * 0.85);
	ALPHA = shell_opacity * (0.18 + energy * 0.82);
}
