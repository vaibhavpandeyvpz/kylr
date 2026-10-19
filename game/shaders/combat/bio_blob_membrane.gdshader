shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix;

uniform vec4 primary_color : source_color = vec4(0.72, 1.0, 0.08, 1.0);
uniform vec4 secondary_color : source_color = vec4(0.14, 0.72, 0.025, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.01, 0.09, 0.02, 1.0);
uniform float emission_energy : hint_range(0.0, 12.0) = 3.8;
uniform float color_curve : hint_range(0.1, 8.0) = 1.5;
uniform float animation_speed : hint_range(0.0, 8.0) = 1.0;
uniform vec2 noise_scale = vec2(2.8, 2.2);
uniform vec2 noise_scroll = vec2(0.23, -0.17);
uniform float noise_curve : hint_range(0.1, 4.0) = 1.2;
uniform float deformation : hint_range(0.0, 0.8) = 0.24;
uniform float pulse_amount : hint_range(0.0, 0.35) = 0.08;
uniform float lobe_frequency : hint_range(1.0, 16.0) = 5.0;
uniform float phase_offset = 0.0;
uniform float rim_power : hint_range(0.25, 8.0) = 2.0;
uniform float vein_width : hint_range(0.01, 0.48) = 0.14;
uniform float shell_opacity : hint_range(0.0, 1.0) = 0.58;

varying vec3 local_surface_position;

float hash31(vec3 p) {
	return fract(sin(dot(p, vec3(127.1, 311.7, 74.7)) + phase_offset * 19.19) * 43758.5453);
}

float value_noise(vec3 p) {
	vec3 cell = floor(p);
	vec3 fraction = fract(p);
	fraction = fraction * fraction * (3.0 - 2.0 * fraction);
	float x00 = mix(hash31(cell), hash31(cell + vec3(1.0, 0.0, 0.0)), fraction.x);
	float x10 = mix(hash31(cell + vec3(0.0, 1.0, 0.0)), hash31(cell + vec3(1.0, 1.0, 0.0)), fraction.x);
	float x01 = mix(hash31(cell + vec3(0.0, 0.0, 1.0)), hash31(cell + vec3(1.0, 0.0, 1.0)), fraction.x);
	float x11 = mix(hash31(cell + vec3(0.0, 1.0, 1.0)), hash31(cell + vec3(1.0, 1.0, 1.0)), fraction.x);
	return mix(mix(x00, x10, fraction.y), mix(x01, x11, fraction.y), fraction.z);
}

float fbm(vec3 p) {
	float value = value_noise(p) * 0.54;
	p = p * 2.03 + vec3(7.1, 13.7, 5.9);
	value += value_noise(p) * 0.27;
	p = p * 2.11 + vec3(17.3, 5.9, 11.7);
	value += value_noise(p) * 0.13;
	p = p * 2.07 + vec3(3.7, 19.1, 7.3);
	value += value_noise(p) * 0.06;
	return value;
}

vec3 flow_offset() {
	float time = TIME * animation_speed;
	return vec3(noise_scroll.x, noise_scroll.y, noise_scroll.x - noise_scroll.y) * time;
}

vec3 noise_position(vec3 unit_position) {
	return vec3(
		unit_position.x * noise_scale.x,
		unit_position.y * noise_scale.y,
		unit_position.z * mix(noise_scale.x, noise_scale.y, 0.5)
	) + flow_offset();
}

void vertex() {
	float radius = max(length(VERTEX), 0.001);
	vec3 unit_position = normalize(VERTEX);
	vec3 sample_position = noise_position(unit_position);
	float coarse = fbm(sample_position);
	float detail = fbm(sample_position * 2.17 + vec3(9.2, 2.7, 6.1));
	float lobes = (
		sin((unit_position.x + unit_position.y * 0.61) * lobe_frequency + TIME * animation_speed * 1.7 + phase_offset)
		+ sin((unit_position.z - unit_position.y * 0.43) * (lobe_frequency * 0.73) - TIME * animation_speed * 1.23)
	) * 0.25;
	float boiling = (pow(max(coarse, 0.001), noise_curve) - 0.47) * 1.65 + (detail - 0.5) * 0.42 + lobes;
	float pulse = sin(TIME * animation_speed * 3.1 + phase_offset + coarse * 6.0) * pulse_amount;
	VERTEX += NORMAL * radius * boiling * deformation * 1.16;
	VERTEX *= 1.0 + pulse;
	local_surface_position = VERTEX;
}

void fragment() {
	vec3 unit_position = normalize(local_surface_position);
	vec3 sample_position = noise_position(unit_position);
	float coarse = pow(max(fbm(sample_position), 0.001), noise_curve);
	float detail = fbm(sample_position * 3.07 + vec3(3.1, 11.7, 5.4));
	float cells = abs(sin((coarse * 1.35 + detail * 0.65) * 18.0 + phase_offset));
	float veins = 1.0 - smoothstep(vein_width, vein_width + 0.16, cells);
	float facing = abs(dot(normalize(NORMAL), normalize(VIEW)));
	float rim = pow(1.0 - facing, rim_power);
	float boiling_pockets = smoothstep(0.62, 0.94, pow(coarse, color_curve) + detail * 0.24);
	float alpha = clamp(rim * 0.9 + veins * 0.5 + boiling_pockets * 0.24, 0.0, 1.0) * shell_opacity;
	vec3 tint = mix(secondary_color.rgb, primary_color.rgb, clamp(veins + rim * 0.72, 0.0, 1.0));
	tint = mix(tint, tertiary_color.rgb, (1.0 - rim) * 0.08);
	ALBEDO = tint * emission_energy * 0.58;
	ALPHA = alpha;
}
