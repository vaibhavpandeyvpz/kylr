// Original seam-free directional star field with procedural wisps.
shader_type sky;
global uniform float arena_sky_time;
uniform bool reduced_motion = false;
uniform float reflection_fill_energy = 0.45;
uniform float reflection_detail_strength = 1.0;
uniform sampler2D wisps : filter_linear_mipmap, repeat_enable;
#include "res://shaders/reflection_environment.gdshaderinc"
float star_hash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
void sky() {
	vec3 ray = normalize(EYEDIR);
	vec3 cell = floor(ray * 450.0);
	vec3 center = cell + vec3(star_hash(cell), star_hash(cell + 17.0), star_hash(cell + 37.0));
	float distance_to_star = length(ray * 450.0 - center);
	float star = exp(-distance_to_star * distance_to_star * 130.0) * step(0.985, star_hash(cell + 71.0));
	vec3 visible_sky = vec3(0.002, 0.003, 0.006) + vec3(0.65, 0.76, 1.0) * star * 1.8;
	vec3 reflection_sky = visible_sky;
	float clock = reduced_motion ? 0.0 : arena_sky_time;
	vec2 direction_uv = vec2(atan(ray.x,ray.z)/TAU,acos(clamp(ray.y,-1.0,1.0))/PI);
	float haze = texture(wisps,direction_uv*vec2(3.0,2.0)+vec2(clock*0.0003,0)).r;
	float detail = texture(wisps,direction_uv*vec2(6.0,4.0)-vec2(clock*0.0002,0)).g;
	visible_sky += vec3(0.012,0.014,0.019) * smoothstep(0.35,0.78,haze+detail*0.2);
	if (AT_CUBEMAP_PASS) {
		vec3 smooth_fill = mix(vec3(0.10, 0.12, 0.16), vec3(0.40, 0.46, 0.56), smoothstep(-0.6, 0.8, ray.y));
		COLOR = reflection_sky + mix(smooth_fill, metal_reflection_environment(ray), reflection_detail_strength) * reflection_fill_energy;
	} else { COLOR = visible_sky; }
}
