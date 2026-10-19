// Shared fixed image-based reflection map, sampled only for the radiance
// cubemap. The visible cosmic sky and scene-light count are unchanged.
uniform sampler2D reflection_panorama : source_color, filter_linear, repeat_enable;

vec3 metal_reflection_environment(vec3 ray) {
	float elevation = smoothstep(-0.6, 0.8, ray.y);
	vec3 base = mix(vec3(0.10, 0.12, 0.16), vec3(0.40, 0.46, 0.56), elevation);
	vec2 uv = vec2(atan(ray.z, ray.x) / 6.28318530718 + 0.5, acos(clamp(ray.y, -1.0, 1.0)) / 3.14159265359);
	// Fade the narrow panorama seam and poles into the neutral floor.
	float edge = smoothstep(0.0, 0.025, min(uv.x, 1.0 - uv.x));
	edge *= smoothstep(0.0, 0.04, min(uv.y, 1.0 - uv.y));
	vec3 pattern = textureLod(reflection_panorama, uv, 0.0).rgb;
	return base * 0.55 + pattern * 3.0 * edge;
}
