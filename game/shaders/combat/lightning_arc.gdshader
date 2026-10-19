shader_type spatial;
render_mode unshaded, cull_disabled, blend_add, shadows_disabled;

// A low-poly cylinder is displaced in the vertex stage, then broken into a
// noisy emissive arc.
uniform vec4 arc_color : source_color = vec4(0.55, 0.88, 1.0, 1.0);
uniform sampler2D noise_texture : repeat_enable;
uniform float arc_seed = 0.0;
uniform float arc_intensity : hint_range(0.0, 1.0) = 1.0;
uniform float arc_amplitude = 0.12;
uniform float arc_opacity : hint_range(0.0, 1.0) = 1.0;
uniform float scroll_speed = 12.0;
uniform float core_continuity : hint_range(0.0, 1.0) = 0.0;
instance uniform float progress = 0.0;


float triangle_wave(float value) {
	return abs(fract(value) * 2.0 - 1.0) - 0.5;
}


void vertex() {
	// Cylinder side UV occupies half the atlas; use geometry for full beam length.
	float along = clamp(0.5 - VERTEX.y, 0.0, 1.0);
	float time = TIME * scroll_speed + arc_seed;
	float envelope = smoothstep(0.05, 0.10, min(along, 1.0 - along));
	// Merge the strand paths at both ends without shrinking any tube diameter.
	float offset_x = triangle_wave(along * 8.0 + time * 0.07)
		+ triangle_wave(along * 13.0 - time * 0.11) * 0.45;
	float offset_z = triangle_wave(along * 10.0 - time * 0.09)
		+ triangle_wave(along * 17.0 + time * 0.06) * 0.35;
	float grain = texture(noise_texture, vec2(UV.x * 2.0 + arc_seed, along * 5.0 + time * 0.03)).r - 0.5;
	VERTEX.xz += vec2(offset_x, offset_z) * arc_amplitude * envelope;
	VERTEX.xz += NORMAL.xz * grain * arc_amplitude * 0.55 * envelope;
}


void fragment() {
	float along = clamp(UV.y * 2.0, 0.0, 1.0);
	float time = TIME * scroll_speed + arc_seed;
	float grain = texture(noise_texture, vec2(UV.x * 3.0 + time * 0.025, along * 7.0)).r;
	float breaks = max(core_continuity, smoothstep(0.28, 0.7, grain));
	// Keep the electrical core connected to both the muzzle and the collision point.
	float contact = 1.0 - smoothstep(0.0, 0.035, min(along, 1.0 - along));
	breaks = max(breaks, contact);
	float fresnel = pow(1.0 - abs(dot(normalize(NORMAL), normalize(VIEW))), 2.0);
	float energy = (0.55 + 0.45 * fresnel) * breaks * arc_intensity * (1.0 - progress);
	ALBEDO = arc_color.rgb;
	EMISSION = arc_color.rgb * energy * 11.0;
	ALPHA = energy * arc_opacity;
}
