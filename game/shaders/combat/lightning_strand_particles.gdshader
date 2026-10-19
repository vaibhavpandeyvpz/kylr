shader_type particles;
render_mode disable_velocity;

uniform float beam_length = 1.0;
uniform float strand_seed_1 = 0.0;
uniform float strand_seed_2 = 0.0;
uniform float core_seed = 0.0;
uniform float particle_seed = 0.0;

float random_value(float value) {
	return fract(sin(value * 127.1 + particle_seed * 311.7) * 43758.5453);
}

float triangle_wave(float value) {
	return abs(fract(value) * 2.0 - 1.0) - 0.5;
}

vec2 wave_offset(float along, float seed, float amplitude) {
	float time = TIME * 12.0 + seed;
	return vec2(
		triangle_wave(along * 8.0 + time * 0.07) + triangle_wave(along * 13.0 - time * 0.11) * 0.45,
		triangle_wave(along * 10.0 - time * 0.09) + triangle_wave(along * 17.0 + time * 0.06) * 0.35
	) * amplitude * smoothstep(0.05, 0.10, min(along, 1.0 - along));
}

void process() {
	if (RESTART) {
		CUSTOM.x = random_value(float(NUMBER) + 1.0);
		CUSTOM.y = 0.0;
		CUSTOM.z = random_value(float(NUMBER) + 19.0);
		CUSTOM.w = random_value(float(NUMBER) + 41.0);
	} else {
		CUSTOM.y += DELTA / LIFETIME;
	}
	// Match the two outer lightning_arc vertex fields; never attach to layer zero.
	// Sparkles span the full beam, including both converged endpoint sections.
	float position_along = CUSTOM.x;
	float along = 1.0 - position_along;
	bool second = CUSTOM.z > 0.5;
	float seed = second ? strand_seed_2 : strand_seed_1;
	float amplitude = second ? 0.28 : 0.2;
	vec2 displacement = wave_offset(along, seed, amplitude);
	float angle = CUSTOM.w * TAU + CUSTOM.y * 1.5;
	vec3 outward = vec3(cos(angle), 0.0, sin(angle));
	vec2 offset = displacement + outward.xz * (0.045 + CUSTOM.y * 0.015);
	// Leave a clear channel around the central beam even when a strand crosses it.
	vec2 core = wave_offset(along, core_seed, 0.1);
	vec2 separation = offset - core;
	float radius = length(separation);
	if (radius < 0.1) offset = core + (radius > 0.001 ? separation / radius : outward.xz) * 0.1;
	float size = mix(0.04, 0.065, CUSTOM.z) * mix(0.7, 1.0, CUSTOM.y);
	vec3 tangent = vec3(-outward.z, 0.0, outward.x);
	TRANSFORM = mat4(vec4(tangent * size, 0.0), vec4(outward * size, 0.0), vec4(vec3(0.0, 1.0, 0.0) * size, 0.0), vec4(offset.x, position_along * beam_length, offset.y, 1.0));
	COLOR = vec4(1.0);
}
