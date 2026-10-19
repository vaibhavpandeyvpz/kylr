shader_type spatial;
render_mode cull_disabled, depth_prepass_alpha;

uniform vec4 primary_color : source_color = vec4(1.0, 0.35, 0.06, 1.0);
uniform vec4 secondary_color : source_color = vec4(0.8, 0.05, 0.01, 1.0);
uniform vec4 core_color : source_color = vec4(1.0);
uniform vec4 tertiary_color : source_color = vec4(0.075, 0.065, 0.06, 1.0);
uniform float emission_energy : hint_range(0.0, 16.0) = 4.0;
uniform float effect_opacity : hint_range(0.0, 1.0) = 1.0;
instance uniform float effect_progress : hint_range(0.0, 1.0) = 0.0;
uniform float effect_start : hint_range(0.0, 1.0) = 0.0;
uniform float effect_end : hint_range(0.0, 1.0) = 1.0;
uniform vec2 noise_scale = vec2(2.0, 1.5);
uniform vec2 noise_scroll = vec2(0.08, -0.18);
uniform float noise_shape : hint_range(0.25, 4.0) = 1.2;
instance uniform float noise_seed = 3.7;
uniform float displacement : hint_range(0.0, 2.0) = 0.55;
uniform bool stepped_shading = true;
uniform float shadow_steps : hint_range(2.0, 12.0) = 4.0;
uniform float hot_pockets = 0.5;
uniform float erosion_bias = 0.0;

varying float surface_noise;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)) + noise_seed * 23.71) * 43758.5453);
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
	float value = value_noise(p) * 0.52;
	p = p * 2.02 + vec2(8.3, 14.1);
	value += value_noise(p) * 0.26;
	p = p * 2.09 + vec2(18.7, 4.6);
	value += value_noise(p) * 0.14;
	p = p * 2.13 + vec2(2.5, 20.3);
	value += value_noise(p) * 0.08;
	return value;
}

void vertex() {
	float local_progress = clamp((effect_progress - effect_start) / max(effect_end - effect_start, 0.001), 0.0, 1.0);
	vec2 flow_uv = UV * noise_scale + noise_scroll * local_progress * 3.0 + COLOR.r * 0.31;
	surface_noise = fbm(flow_uv);
	float edge_mask = sin(UV.y * 3.14159265);
	VERTEX += NORMAL * (surface_noise - 0.42) * displacement * edge_mask;
}

void fragment() {
	float local_progress = clamp((effect_progress - effect_start) / max(effect_end - effect_start, 0.001), 0.0, 1.0);
	vec2 flow_uv = UV * noise_scale + noise_scroll * local_progress * 3.0 + COLOR.r * 0.31;
	float coarse = pow(max(fbm(flow_uv), 0.001), noise_shape);
	float detail = fbm(flow_uv * 3.17 + vec2(13.0, 7.0));
	float breakup = coarse * 0.78 + detail * 0.34;
	float dissolve = local_progress * 0.58 + (1.0 - COLOR.a) * 0.35 + erosion_bias;
	float alpha = smoothstep(dissolve + 0.04, dissolve + 0.3, breakup);
	float heat = smoothstep(0.48 + local_progress * 0.32, 0.94, breakup) * hot_pockets;
	vec3 smoke_tint = mix(tertiary_color.rgb, secondary_color.rgb, heat * 0.55);
	smoke_tint = mix(smoke_tint, primary_color.rgb, heat);
	float rim = pow(1.0 - abs(dot(normalize(NORMAL), normalize(VIEW))), 2.0);
	smoke_tint += tertiary_color.rgb * rim * 0.72;
	ALBEDO = smoke_tint;
	EMISSION = tertiary_color.rgb * (0.18 + rim * 0.32) + primary_color.rgb * emission_energy * heat * heat;
	float birth = smoothstep(effect_start, min(effect_start + 0.06, effect_end), effect_progress);
	ALPHA = alpha * birth * effect_opacity * tertiary_color.a * 0.82;
	ALPHA_SCISSOR_THRESHOLD = 0.28;
	float dx = dFdx(breakup);
	float dy = dFdy(breakup);
	NORMAL_MAP = normalize(vec3(-dx * 4.0, -dy * 4.0, 1.0));
	SPECULAR = 0.05;
	ROUGHNESS = 0.92;
}

void light() {
	float diffuse = max(dot(NORMAL, LIGHT), 0.0) * ATTENUATION;
	if (stepped_shading) {
		diffuse = floor(diffuse * shadow_steps) / max(shadow_steps - 1.0, 1.0);
	}
	DIFFUSE_LIGHT += LIGHT_COLOR * diffuse;
}
