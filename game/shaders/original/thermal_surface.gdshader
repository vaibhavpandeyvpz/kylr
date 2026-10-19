// Original bounded thermal plume. Temperature and opacity are independent.
shader_type spatial;
render_mode unshaded, blend_mix, cull_back, depth_draw_never;
uniform vec4 primary_color : source_color = vec4(1.0, 0.78, 0.28, 1.0);
uniform vec4 secondary_color : source_color = vec4(1.0, 0.13, 0.015, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.08, 0.025, 0.008, 1.0);
uniform float emission = 1.5;
uniform float effect_opacity = 1.0;
uniform float effect_emission = 1.0;
uniform float speed_scale = 1.0;
uniform float phase = 0.0;
uniform bool axial = false;
uniform bool clip_enabled = false;
uniform vec3 clip_origin;
uniform vec3 clip_direction = vec3(0.0, 1.0, 0.0);
uniform float clip_length = 1.0;
uniform float beam_length = 1.0;
uniform float start_radius = 0.035;
uniform float end_radius = 0.17;
uniform int plume_shape = 0; // tapered jet, lobed envelope, twisted membranes
uniform bool continuous_beam = false;
uniform sampler2D turbulence_texture : filter_linear_mipmap, repeat_enable;
instance uniform float progress = 0.0;
varying vec3 world_position;
void vertex() {
	if (axial) {
		float t = clamp(VERTEX.z,0.0,1.0);
		float radius_ratio = plume_shape == 0 ? mix(start_radius,end_radius,t) / (0.12+0.38*t) : end_radius / (plume_shape == 1 ? 0.75 : 0.5);
		VERTEX = vec3(VERTEX.x*radius_ratio,t*beam_length,-VERTEX.y*radius_ratio);
		NORMAL = vec3(NORMAL.x,NORMAL.z,-NORMAL.y);
	}
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
void fragment() {
	float t = TIME * speed_scale;
	vec2 frequency = vec2(2.17,continuous_beam ? clamp(beam_length*0.65,1.0,12.0) : 4.31);
	vec2 advected = UV*frequency-vec2(0.04,t*0.9)+vec2(phase,phase*0.713);
	// Axial UV.y decreases toward the tip: positive UV advection carries
	// the pattern away from the nozzle. Large eddies evolve more slowly
	// than the faster particle transport, avoiding temporal strobing.
	if (continuous_beam) advected.y = UV.y*frequency.y+t*6.0*frequency.y/max(beam_length,0.01)+phase*0.713;
	vec4 flow = texture(turbulence_texture,advected);
	float turbulence = texture(turbulence_texture,advected*1.37+(flow.gb-0.5)*0.65).r;
	float age = axial ? 1.0-UV.y : progress;
	float hot = clamp(1.0 - age * (continuous_beam ? 0.5 : 0.9) + turbulence * 0.25, 0.0, 1.0);
	vec3 heat = mix(secondary_color.rgb, primary_color.rgb, hot * hot);
	float breakup = smoothstep(0.24+age*0.1,0.48+age*0.1,turbulence);
	if (continuous_beam) breakup = mix(0.02,1.0,smoothstep(0.2,0.8,turbulence));
	float opacity = (1.0 - smoothstep(continuous_beam ? 0.95 : 0.65,1.0,age)) * breakup * effect_opacity;
	if (clip_enabled) {
		float along = dot(world_position - clip_origin, clip_direction);
		opacity *= step(0.0, along) * step(along, clip_length);
		opacity *= 1.0 - smoothstep(10.0, 15.0, along);
	}
	float rim = pow(1.0-abs(dot(normalize(NORMAL),normalize(VIEW))),0.45);
	// A gas volume thins at its silhouette; an opaque bright rim exposes
	// the polygon shell, especially when looking along the muzzle.
	opacity *= continuous_beam ? mix(0.12,1.0,pow(abs(dot(normalize(NORMAL),normalize(VIEW))),0.5)) : mix(1.0,rim,0.65);
	ALBEDO = heat * (1.0 + hot * emission * effect_emission * 3.0);
	EMISSION = heat * emission * effect_emission * (0.2 + hot * 1.8);
	ALPHA = opacity * 0.68;
}
