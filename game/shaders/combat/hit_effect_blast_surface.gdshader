shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add;

uniform vec4 primary_color : source_color = vec4(1.0, 0.42, 0.08, 1.0);
uniform vec4 secondary_color : source_color = vec4(1.0, 0.06, 0.01, 1.0);
uniform vec4 core_color : source_color = vec4(1.0);
uniform vec4 tertiary_color : source_color = vec4(0.08, 0.05, 0.04, 1.0);
uniform float emission_energy : hint_range(0.0, 16.0) = 5.0;
uniform float effect_opacity : hint_range(0.0, 1.0) = 1.0;
instance uniform float effect_progress : hint_range(0.0, 1.0) = 0.0;
uniform vec2 noise_scale = vec2(2.2, 1.6);
uniform vec2 noise_scroll = vec2(0.12, -0.28);
uniform float noise_shape : hint_range(0.25, 4.0) = 1.35;
instance uniform float noise_seed = 3.7;
uniform float displacement = 0.0;
uniform float streaks = 11.0;
uniform float twist = 0.0;
uniform float band_width = 0.18;
uniform float erosion_bias = 0.0;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)) + noise_seed * 31.3) * 43758.5453);
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
	float value = value_noise(p) * 0.58;
	p = p * 2.07 + vec2(9.2, 4.1);
	value += value_noise(p) * 0.28;
	p = p * 2.13 + vec2(3.8, 17.6);
	value += value_noise(p) * 0.14;
	return value;
}

void vertex() {
	float flutter = sin((UV.x * streaks + UV.y * twist + effect_progress * 2.0) * 6.2831853);
	VERTEX += NORMAL * flutter * displacement * (1.0 - effect_progress);
}

void fragment() {
	vec2 flow_uv = UV * noise_scale + noise_scroll * effect_progress * 3.0;
	float grain = pow(max(fbm(flow_uv), 0.001), noise_shape);
	float wave = sin((UV.x * streaks + UV.y * twist) * 6.2831853) * 0.5 + 0.5;
	float center_band = 1.0 - smoothstep(band_width, band_width * 2.8, abs(UV.y - 0.5 + (wave - 0.5) * 0.14));
	float edge_teeth = smoothstep(0.38, 0.9, wave) * (1.0 - smoothstep(0.18, 0.48, abs(UV.y - 0.5)));
	float erosion = smoothstep(0.22 + effect_progress * 0.62 + erosion_bias, 0.72 + effect_progress * 0.35 + erosion_bias, grain + center_band * 0.52);
	float fade = 1.0 - smoothstep(0.48, 1.0, effect_progress);
	float mask = max(center_band, edge_teeth * grain) * erosion * fade;
	vec3 tint = mix(secondary_color.rgb, primary_color.rgb, grain + center_band * 0.3);
	tint = mix(tint, core_color.rgb, center_band * smoothstep(0.66, 1.0, grain));
	ALBEDO = tint;
	EMISSION = tint * emission_energy;
	ALPHA = mask * effect_opacity * primary_color.a;
}
