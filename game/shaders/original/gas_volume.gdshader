// Original fire/smoke atlas, one layer in a depth-tested burst composition.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;
uniform sampler2D volume_atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform float effect_opacity = 1.0;
uniform float effect_emission = 1.0;
uniform float emission = 2.6;
uniform int event_profile = 0; // rocket combustion, brief detonation, fuel flare
uniform bool particle_volume = false;
uniform bool projected_jet = false;
uniform bool surface_aligned = false;
uniform float anchor_offset_y = 0.0;
uniform bool clip_enabled = false;
uniform vec3 clip_origin;
uniform vec3 clip_direction = vec3(0.0,1.0,0.0);
uniform float clip_length = 1.0;
instance uniform float progress = 0.0;
varying float gas_progress;
varying vec3 world_position;
void vertex() {
	VERTEX = vec3(VERTEX.x,VERTEX.z-0.5,0.0);
	VERTEX.y += anchor_offset_y;
	gas_progress = particle_volume ? INSTANCE_CUSTOM.y : progress;
	if (particle_volume) VERTEX.xy *= vec2(0.65,0.9);
	vec2 projected_axis = (VIEW_MATRIX*MODEL_MATRIX)[1].xy;
	if (projected_jet) {
		// Stretch in world space, then foreshorten toward the firing axis.
		// Keeping the full length in screen space makes end-on gas look like
		// pointed leaves instead of overlapping volumes moving away from us.
		float side_view = length(projected_axis) / max(length(MODEL_MATRIX[1].xyz),0.001);
		float width = mix(0.5,1.2,smoothstep(0.0,0.65,gas_progress));
		float length_m = mix(1.6,2.6,gas_progress);
		VERTEX.xy *= vec2(width,sqrt(2.0*width*width+length_m*length_m*side_view*side_view));
	}
	MODELVIEW_MATRIX = VIEW_MATRIX*mat4(INV_VIEW_MATRIX[0],INV_VIEW_MATRIX[1],INV_VIEW_MATRIX[2],MODEL_MATRIX[3]);
	MODELVIEW_MATRIX[0].xyz *= length(MODEL_MATRIX[0].xyz);
	MODELVIEW_MATRIX[1].xyz *= length(MODEL_MATRIX[1].xyz);
	MODELVIEW_MATRIX[2].xyz *= length(MODEL_MATRIX[2].xyz);
	if ((projected_jet || (surface_aligned && MODEL_MATRIX[1].y>length(MODEL_MATRIX[1].xyz)*0.5)) && length(projected_axis)>0.01) {
		vec2 axis = normalize(projected_axis);
		MODELVIEW_MATRIX[0].xyz = vec3(axis.y,-axis.x,0.0)*length(MODEL_MATRIX[0].xyz);
		MODELVIEW_MATRIX[1].xyz = vec3(axis,0.0)*length(MODEL_MATRIX[1].xyz);
	}
	world_position = (INV_VIEW_MATRIX*MODELVIEW_MATRIX*vec4(VERTEX,1.0)).xyz;
}
vec4 frame_sample(float frame, vec2 local_uv) {
	vec2 cell = vec2(mod(frame,4.0),floor(frame/4.0));
	return texture(volume_atlas,(clamp(local_uv,vec2(0.008),vec2(0.992))+cell)/4.0);
}
void fragment() {
	float frame = clamp(gas_progress*15.0,0.0,15.0);
	// Gas is already ignited at the pilot. The impact atlas's compact ignition
	// frames otherwise leave a visible gap at the muzzle and near contacts.
	if (projected_jet) frame = mix(2.0,12.0,gas_progress);
	vec4 gas = mix(frame_sample(floor(frame),UV),frame_sample(min(floor(frame)+1.0,15.0),UV),fract(frame));
	if (projected_jet) {
		// Soft ellipsoidal density hides the edges of successive atlas cards.
		vec2 radial = (UV-0.5)*2.0;
		gas.a *= 1.0-smoothstep(0.25,1.0,dot(radial,radial));
	}
	if (gas.a < 0.01) discard;
	float heat = (1.0-smoothstep(0.15,0.55,gas_progress))*clamp((gas.r-gas.b)*2.0,0.0,1.0);
	if (event_profile == 1) heat = (1.0-smoothstep(0.0,0.18,gas_progress))*pow(max(gas.r,max(gas.g,gas.b)),4.0);
	if (event_profile == 2) heat = (1.0-smoothstep(0.45,0.95,gas_progress))*clamp((gas.r-gas.b)*2.0,0.0,1.0);
	float fade = 1.0-smoothstep(0.65,1.0,gas_progress);
	if (particle_volume) fade *= smoothstep(0.0,projected_jet ? 0.035 : 0.1,gas_progress);
	if (clip_enabled) {
		float along = dot(world_position-clip_origin,clip_direction);
		fade *= step(0.0,along)*(1.0-smoothstep(max(0.0,clip_length-0.25),clip_length,along));
	}
	ALBEDO = gas.rgb;
	EMISSION = gas.rgb*heat*emission*effect_emission;
	ALPHA = gas.a*effect_opacity*fade;
}
