// Adapted from KYLR: Galaxy rebound_orb_wake; Arena lightning palette.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_mix, shadows_disabled;

uniform vec4 spark_color : source_color = vec4(0.741, 0.937, 1.0, 1.0);
uniform vec4 flame_color : source_color = vec4(0.455, 0.749, 1.0, 1.0);
uniform vec4 fume_color : source_color = vec4(0.025, 0.055, 0.09, 0.24);
uniform float emission_energy : hint_range(0.0, 20.0) = 9.0;
instance uniform float seed = 0.0;

float hash21(vec2 point) {
	return fract(sin(dot(point, vec2(127.1, 311.7)) + seed * 23.17) * 43758.5453);
}

float value_noise(vec2 point) {
	vec2 cell = floor(point);
	vec2 fraction = fract(point);
	fraction = fraction * fraction * (3.0 - 2.0 * fraction);
	return mix(
		mix(hash21(cell), hash21(cell + vec2(1.0, 0.0)), fraction.x),
		mix(hash21(cell + vec2(0.0, 1.0)), hash21(cell + vec2(1.0, 1.0)), fraction.x),
		fraction.y
	);
}

void vertex() {
	vec3 model_scale = vec3(
		length(MODEL_MATRIX[0].xyz),
		length(MODEL_MATRIX[1].xyz),
		length(MODEL_MATRIX[2].xyz)
	);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
		vec4(INV_VIEW_MATRIX[0].xyz * model_scale.x, 0.0),
		vec4(INV_VIEW_MATRIX[1].xyz * model_scale.y, 0.0),
		vec4(INV_VIEW_MATRIX[2].xyz * model_scale.z, 0.0),
		MODEL_MATRIX[3]
	);
}

void fragment() {
	float age = clamp(COLOR.r, 0.0, 1.0);
	vec2 point = (UV - vec2(0.5)) * 2.0;
	float angle = age * 4.8 + seed;
	float cs = cos(angle);
	float sn = sin(angle);
	point = mat2(vec2(cs, -sn), vec2(sn, cs)) * point;
	float radius = length(point);
	vec2 flow_uv = point * mix(5.4, 2.7, age) + vec2(TIME * 0.82, -TIME * 0.47) + seed;
	float noise = value_noise(flow_uv) * 0.68 + value_noise(flow_uv * 2.17 + 9.0) * 0.32;
	float spark_phase = 1.0 - smoothstep(0.18, 0.48, age);
	float fume_phase = smoothstep(0.22, 0.68, age);
	float spark_shape = 1.0 - smoothstep(0.07, mix(0.22, 0.38, noise), radius);
	float torn_radius = radius + (noise - 0.5) * 0.52;
	float fume_shape = 1.0 - smoothstep(0.28, 1.0, torn_radius);
	float mask = mix(spark_shape, fume_shape, fume_phase) * COLOR.a;
	vec3 burning_tint = mix(flame_color.rgb, spark_color.rgb, spark_phase * 0.82 + noise * 0.18);
	vec3 tint = mix(burning_tint, fume_color.rgb, fume_phase);
	ALBEDO = tint;
	EMISSION = burning_tint * emission_energy * mask * spark_phase;
	ALPHA = mask * mix(0.94, fume_color.a, fume_phase);
}
