shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add;

uniform vec4 primary_color : source_color = vec4(1.0, 0.8, 0.3, 1.0);
uniform vec4 secondary_color : source_color = vec4(1.0, 0.15, 0.02, 1.0);
uniform vec4 core_color : source_color = vec4(1.0);
uniform float emission_energy : hint_range(0.0, 12.0) = 5.0;
uniform float effect_opacity : hint_range(0.0, 1.0) = 1.0;
uniform float edge_hardness : hint_range(0.0, 1.0) = 0.6;
uniform float flash_pinch : hint_range(0.0, 1.0) = 0.45;
uniform float effect_progress : hint_range(0.0, 1.0) = 0.0;
uniform float rotation_offset = 0.0;
uniform float spin = 0.0;
uniform float shape_mode : hint_range(0.0, 5.0) = 0.0;
uniform float seed = 0.0;

varying float v_progress;

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
	float value = 0.0;
	value += value_noise(p) * 0.5;
	p = p * 2.03 + vec2(17.2, 9.1);
	value += value_noise(p) * 0.25;
	p = p * 2.01 + vec2(5.7, 13.4);
	value += value_noise(p) * 0.125;
	p = p * 2.07 + vec2(11.3, 2.8);
	value += value_noise(p) * 0.0625;
	return value / 0.9375;
}

void vertex() {
	vec3 model_scale = vec3(
		length(MODEL_MATRIX[0].xyz),
		length(MODEL_MATRIX[1].xyz),
		length(MODEL_MATRIX[2].xyz)
	);
	mat4 billboard = mat4(
		vec4(INV_VIEW_MATRIX[0].xyz * model_scale.x, 0.0),
		vec4(INV_VIEW_MATRIX[1].xyz * model_scale.y, 0.0),
		vec4(INV_VIEW_MATRIX[2].xyz * model_scale.z, 0.0),
		MODEL_MATRIX[3]
	);
	MODELVIEW_MATRIX = VIEW_MATRIX * billboard;
	v_progress = effect_progress;
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float turn = rotation_offset + spin * effect_progress + seed;
	float cs = cos(turn);
	float sn = sin(turn);
	p = mat2(vec2(cs, -sn), vec2(sn, cs)) * p;
	float r = length(p);
	float angle = atan(p.y, p.x);
	float softness = mix(0.12, 0.018, edge_hardness);
	float grain = fbm(p * 7.0 + vec2(seed * 3.1, seed * 5.7) + effect_progress * vec2(1.7, -2.1));
	float fine_grain = value_noise(p * 31.0 + seed * 19.0);

	vec2 star_uv = abs(p);
	float star_field = pow(star_uv.x, 0.42) + pow(star_uv.y, 0.42);
	float star4 = 1.0 - smoothstep(0.72, 1.02, star_field);
	float core = (1.0 - smoothstep(0.0, 0.52 + grain * 0.08, r)) * mix(0.72, 1.0, grain);
	core = max(core * 0.72, star4);
	float ring_radius = mix(0.2, 0.82, effect_progress);
	float torn_radius = r + (grain - 0.5) * 0.16;
	float ring = 1.0 - smoothstep(softness, softness * 2.8, abs(torn_radius - ring_radius));
	float teeth = pow(max(0.0, cos(angle * 14.0 + seed * 9.0)), 18.0);
	float tooth_envelope = 1.0 - smoothstep(ring_radius + 0.08 + teeth * 0.34, ring_radius + 0.14 + teeth * 0.38, r);
	tooth_envelope *= smoothstep(ring_radius - 0.08, ring_radius + 0.02, r);
	float crown = max(ring * mix(0.58, 1.0, grain), teeth * tooth_envelope);
	float spiral_line = abs(sin(angle * 3.0 - r * 18.0 + effect_progress * 9.0 + seed));
	float spiral_envelope = 1.0 - smoothstep(0.96, 1.05, r);
	spiral_envelope *= smoothstep(0.08, 0.28, r);
	float spiral = smoothstep(0.68 - grain * 0.16, 0.96, spiral_line) * spiral_envelope;
	spiral *= smoothstep(0.38, 0.76, grain) * mix(0.5, 1.0, fine_grain);
	float rays_a = pow(max(0.0, cos(angle * 8.0 + seed * 5.0)), 20.0);
	float rays_b = pow(max(0.0, sin(angle * 13.0 - seed * 2.0)), 28.0);
	float ray_variance = 0.38 + 0.5 * value_noise(vec2(angle * 4.0 + seed, seed));
	float rays = max(rays_a, rays_b * 0.72);
	rays *= 1.0 - smoothstep(ray_variance, min(ray_variance + 0.45, 0.98), r);
	rays *= smoothstep(0.03, 0.18, r) * mix(0.7, 1.0, fine_grain);
	float taper = max(0.0, 1.0 - abs(p.x));
	float slash_width = mix(0.025, 0.24, taper * taper) * mix(0.42, 1.0, 1.0 - flash_pinch);
	float slash_noise = (grain - 0.5) * 0.16 * taper;
	float slash = 1.0 - smoothstep(slash_width, slash_width + 0.055, abs(p.y + slash_noise));
	slash *= smoothstep(1.0, 0.72, abs(p.x)) * mix(0.62, 1.0, fine_grain);
	float mote_radius = r + (grain - 0.5) * 0.2;
	float mote = 1.0 - smoothstep(0.22, 0.62, mote_radius);
	mote *= mix(0.58, 1.0, fine_grain);

	float w0 = 1.0 - step(0.5, abs(shape_mode - 0.0));
	float w1 = 1.0 - step(0.5, abs(shape_mode - 1.0));
	float w2 = 1.0 - step(0.5, abs(shape_mode - 2.0));
	float w3 = 1.0 - step(0.5, abs(shape_mode - 3.0));
	float w4 = 1.0 - step(0.5, abs(shape_mode - 4.0));
	float w5 = 1.0 - step(0.5, abs(shape_mode - 5.0));
	float mask = core * w0 + crown * w1 + spiral * w2 + rays * w3 + slash * w4 + mote * w5;
	mask *= 1.0 - smoothstep(0.78, 1.0, effect_progress);
	vec3 tint = mix(secondary_color.rgb, primary_color.rgb, clamp(mask * 0.78 + grain * 0.24, 0.0, 1.0));
	float white_hot = smoothstep(0.62, 1.0, mask) * mix(0.55, 1.0, core + star4);
	tint = mix(tint, core_color.rgb, white_hot * 0.72);
	ALBEDO = tint;
	EMISSION = tint * emission_energy;
	ALPHA = mask * mix(secondary_color.a, primary_color.a, 0.6) * effect_opacity;
}
