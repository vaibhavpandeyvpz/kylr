shader_type spatial;
render_mode unshaded, cull_disabled, blend_add, depth_draw_never;

// Procedural card mask: no texture imports, depth reads, or discard path.
// The card's local Y axis points down the barrel; crossed cards make the
// effect read as a compact 3D flame rather than a camera-facing sticker.
instance uniform vec4 core_color : source_color = vec4(1.0, 0.94, 0.72, 1.0);
instance uniform vec4 flame_color : source_color = vec4(1.0, 0.30, 0.045, 1.0);
instance uniform float emission_energy : hint_range(0.0, 16.0, 0.1) = 7.0;
instance uniform float progress : hint_range(0.0, 1.0, 0.01) = 1.0;
instance uniform float flash_seed = 0.0;
instance uniform int flash_layer : hint_range(0, 2, 1) = 0;

float hash12(vec2 value) {
	return fract(sin(dot(value, vec2(127.1, 311.7)) + flash_seed * 17.0) * 43758.5453);
}

void fragment() {
	// The narrow throat meets the muzzle; hot gas expands away from the barrel.
	vec2 uv = vec2(UV.x, 1.0 - UV.y);
	float edge_noise = hash12(floor(uv * vec2(11.0, 17.0)));
	float travel = clamp(uv.y + (edge_noise - 0.5) * 0.085, 0.0, 1.0);
	float taper = pow(1.0 - travel, 0.60);
	float wander = sin(travel * 22.0 + flash_seed * 4.0) * 0.045 * taper;
	float half_width = mix(0.018, 0.42, taper);
	float tongue = 1.0 - smoothstep(half_width * 0.66, half_width, abs(uv.x - 0.5 - wander));
	float base = smoothstep(0.0, 0.24, uv.y);
	float tip = 1.0 - smoothstep(0.68, 1.0, uv.y);
	float body = tongue * base * tip;
	float core = 1.0 - smoothstep(0.025, 0.16, abs(uv.x - 0.5));
	core *= smoothstep(0.0, 0.22, uv.y) * (1.0 - smoothstep(0.45, 0.88, uv.y));
	float side_tongue = 1.0 - smoothstep(
		0.015,
		0.09 + taper * 0.12,
		abs(uv.x - 0.5 + wander * 2.4 - 0.17 * taper)
	);
	side_tongue *= smoothstep(0.08, 0.28, uv.y) * (1.0 - smoothstep(0.40, 0.82, uv.y));
	float front_distance = length((uv - vec2(0.5)) * vec2(1.0, 0.9));
	float front_bloom = 1.0 - smoothstep(0.18, 0.50, front_distance);
	float front_rays = 0.72 + 0.28 * sin(atan(uv.y - 0.5, uv.x - 0.5) * 6.0 + flash_seed);
	front_bloom *= front_rays;
	float shape = body;
	if (flash_layer == 1) {
		shape = max(side_tongue, body * 0.42);
	} else if (flash_layer == 2) {
		shape = front_bloom;
	}
	float flicker = 0.83 + 0.17 * sin(flash_seed * 23.0 + uv.y * 19.0);
	float fade = 1.0 - smoothstep(0.18, 1.0, progress);
	float alpha = shape * flicker * fade;
	float hot_core = flash_layer == 2 ? front_bloom * 0.58 : core;
	vec3 colour = mix(flame_color.rgb, core_color.rgb, hot_core);
	ALBEDO = colour;
	float emission_shape = shape + hot_core * 0.85;
	if (flash_layer == 2) {
		emission_shape *= 0.55;
	}
	EMISSION = colour * emission_energy * emission_shape * fade;
	ALPHA = alpha;
}
