shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never;
instance uniform float progress = 0.0;
instance uniform vec4 tint : source_color = vec4(1.0, 0.5, 0.12, 1.0);
instance uniform float seed = 0.0;
instance uniform float style = 0.0;
uniform bool billboard = false;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise_at(vec2 p) {
	vec2 cell = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(cell), hash(cell + vec2(1.0, 0.0)), f.x), mix(hash(cell + vec2(0.0, 1.0)), hash(cell + vec2(1.0)), f.x), f.y);
}
void vertex() {
	if (billboard) {
		vec3 s = vec3(length(MODEL_MATRIX[0].xyz), length(MODEL_MATRIX[1].xyz), length(MODEL_MATRIX[2].xyz));
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(vec4(INV_VIEW_MATRIX[0].xyz * s.x, 0.0), vec4(INV_VIEW_MATRIX[1].xyz * s.y, 0.0), vec4(INV_VIEW_MATRIX[2].xyz * s.z, 0.0), MODEL_MATRIX[3]);
	}
}
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float angle = atan(p.y, p.x);
	float noise = (noise_at(p * 6.0 + seed + progress * 2.0) * 0.7 + noise_at(p * 13.0 - seed) * 0.3) * 2.0 - 1.0;
	float edge = r + noise * 0.065;
	float core = 1.0 - smoothstep(0.0, 0.38, r);
	float mask = 1.0 - smoothstep(0.15, 0.95, edge);
	float energy = 3.0;
	if (style < 0.5) {
		float rays = pow(max(0.0, cos(angle * 7.0 + seed)), 18.0);
		mask *= max(core, rays * (1.0 - r));
	} else if (style < 1.5) {
		mask *= 0.27;
		energy = 0.0;
	} else if (style < 2.5) {
		mask = 1.0 - smoothstep(0.045, 0.13, abs(edge - mix(0.15, 0.78, progress)));
	} else if (style < 3.5) {
		mask = (1.0 - smoothstep(0.26, 0.82, edge)) * (0.7 + noise * 0.2);
		energy = 0.0;
	}
	float fade = style > 2.5 && style < 3.5 ? 1.0 - smoothstep(0.75, 1.0, progress) : pow(1.0 - progress, 1.4);
	ALBEDO = mix(tint.rgb, vec3(1.0, 0.94, 0.8), core * 0.65 * step(0.1, energy));
	EMISSION = ALBEDO * energy;
	ALPHA = clamp(mask * fade * tint.a, 0.0, 1.0);
}
