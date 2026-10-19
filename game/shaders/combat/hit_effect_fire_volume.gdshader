shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add;

uniform vec4 primary_color : source_color = vec4(1.0, 0.42, 0.08, 1.0);
uniform vec4 secondary_color : source_color = vec4(1.0, 0.06, 0.01, 1.0);
uniform vec4 core_color : source_color = vec4(1.0, 0.96, 0.78, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.08, 0.05, 0.04, 1.0);
uniform float emission_energy : hint_range(0.0, 16.0) = 6.0;
uniform float effect_opacity : hint_range(0.0, 1.0) = 1.0;
instance uniform float effect_progress : hint_range(0.0, 1.0) = 0.0;
uniform vec2 noise_scale = vec2(2.2, 1.6);
uniform vec2 noise_scroll = vec2(0.12, -0.28);
uniform float noise_shape : hint_range(0.25, 4.0) = 1.35;
instance uniform float noise_seed = 3.7;
uniform float displacement : hint_range(0.0, 1.5) = 0.42;
uniform float expansion = 1.0;
uniform float erosion_bias = 0.0;

varying float vertex_noise;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)) + noise_seed * 17.17) * 43758.5453);
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
	float value = value_noise(p) * 0.54;
	p = p * 2.03 + vec2(7.1, 13.7);
	value += value_noise(p) * 0.27;
	p = p * 2.11 + vec2(17.3, 5.9);
	value += value_noise(p) * 0.13;
	p = p * 2.07 + vec2(3.7, 19.1);
	value += value_noise(p) * 0.06;
	return value;
}

void vertex() {
	vec2 flow_uv = UV * noise_scale + noise_scroll * effect_progress * 4.0;
	vertex_noise = fbm(flow_uv);
	float birth = smoothstep(0.0, 0.1, effect_progress);
	float pulse = sin(effect_progress * 3.14159265);
	VERTEX += NORMAL * (vertex_noise - 0.42) * displacement * pulse;
	VERTEX *= mix(0.08, expansion, birth);
}

void fragment() {
	vec2 flow_uv = UV * noise_scale + noise_scroll * effect_progress * 4.0;
	float coarse = pow(max(fbm(flow_uv), 0.001), noise_shape);
	float detail = fbm(flow_uv * 2.73 + vec2(11.0, 3.0));
	float erosion = smoothstep(0.18 + effect_progress * 0.62 + erosion_bias, 0.56 + effect_progress * 0.46 + erosion_bias, coarse + detail * 0.28);
	float envelope = smoothstep(0.0, 0.07, effect_progress) * (1.0 - smoothstep(0.62, 1.0, effect_progress));
	float mask = erosion * envelope * COLOR.a;
	float heat = clamp(coarse * 0.9 + detail * 0.32 - effect_progress * 0.42, 0.0, 1.0);
	vec3 tint = mix(secondary_color.rgb, primary_color.rgb, smoothstep(0.18, 0.72, heat));
	tint = mix(tint, core_color.rgb, smoothstep(0.68, 1.0, heat));
	ALBEDO = tint;
	EMISSION = tint * emission_energy * mix(0.62, 1.35, heat);
	ALPHA = mask * effect_opacity * primary_color.a;
}
