shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add;

uniform vec4 primary_color : source_color = vec4(1.0, 0.7, 0.2, 1.0);
uniform vec4 secondary_color : source_color = vec4(1.0, 0.1, 0.02, 1.0);
uniform vec4 core_color : source_color = vec4(1.0);
uniform float emission_energy : hint_range(0.0, 12.0) = 5.0;
uniform float effect_opacity : hint_range(0.0, 1.0) = 1.0;
uniform float edge_hardness : hint_range(0.0, 1.0) = 0.55;
uniform float flash_pinch : hint_range(0.0, 1.0) = 0.45;
uniform float effect_progress : hint_range(0.0, 1.0) = 0.0;
uniform float seed = 0.0;

varying vec3 local_position;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float value_noise(vec2 p) {
	vec2 cell = floor(p);
	vec2 fraction = fract(p);
	fraction = fraction * fraction * (3.0 - 2.0 * fraction);
	float a = hash21(cell);
	float b = hash21(cell + vec2(1.0, 0.0));
	float c = hash21(cell + vec2(0.0, 1.0));
	float d = hash21(cell + vec2(1.0, 1.0));
	return mix(mix(a, b, fraction.x), mix(c, d, fraction.x), fraction.y);
}

float fbm(vec2 p) {
	float value = value_noise(p) * 0.5;
	p = p * 2.07 + vec2(7.2, 13.4);
	value += value_noise(p) * 0.25;
	p = p * 2.03 + vec2(17.1, 4.8);
	value += value_noise(p) * 0.125;
	p = p * 2.01 + vec2(2.3, 19.7);
	value += value_noise(p) * 0.0625;
	return value / 0.9375;
}

void vertex() {
	local_position = VERTEX;
	float surface_noise = fbm(UV * vec2(5.0, 8.0) + vec2(seed * 2.0, effect_progress * 2.4));
	VERTEX += NORMAL * (surface_noise - 0.48) * 0.26 * smoothstep(0.0, 0.45, effect_progress);
	VERTEX *= mix(0.2, 1.0, smoothstep(0.0, 0.38, effect_progress));
}

void fragment() {
	float facing = abs(dot(normalize(NORMAL), normalize(VIEW)));
	float rim = pow(1.0 - facing, mix(0.7, 2.8, edge_hardness));
	float surface_noise = fbm(UV * vec2(5.0, 8.0) + vec2(seed * 2.0, effect_progress * 2.4));
	float veins = abs(sin(surface_noise * 15.0 + UV.y * 9.0 - effect_progress * 4.0));
	float threshold = mix(0.48, 0.82, effect_progress);
	float breakup = smoothstep(threshold - 0.1, threshold + 0.08, surface_noise + veins * 0.16);
	float fade = 1.0 - smoothstep(0.64, 1.0, effect_progress);
	float mask = max(rim * 0.48, breakup) * fade;
	float hot_detail = clamp(pow(breakup, 3.0) * 0.58 + rim * 0.22, 0.0, 1.0);
	vec3 tint = mix(secondary_color.rgb, primary_color.rgb, hot_detail);
	tint = mix(tint, core_color.rgb, smoothstep(0.9, 1.0, breakup) * facing * 0.18);
	ALBEDO = tint;
	EMISSION = tint * emission_energy;
	ALPHA = mask * primary_color.a * effect_opacity;
}
