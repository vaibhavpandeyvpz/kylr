// Dedicated depth-tested abrasion dust billboard.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;
uniform sampler2D volume_atlas : source_color, filter_linear_mipmap, repeat_disable;
uniform float effect_opacity = 0.26;
instance uniform float progress = 0.0;
void vertex() {
    VERTEX = vec3(VERTEX.x,VERTEX.z-0.5,0.0);
    MODELVIEW_MATRIX = VIEW_MATRIX*mat4(INV_VIEW_MATRIX[0],INV_VIEW_MATRIX[1],INV_VIEW_MATRIX[2],MODEL_MATRIX[3]);
    MODELVIEW_MATRIX[0].xyz *= length(MODEL_MATRIX[0].xyz);
    MODELVIEW_MATRIX[1].xyz *= length(MODEL_MATRIX[1].xyz);
    MODELVIEW_MATRIX[2].xyz *= length(MODEL_MATRIX[2].xyz);
}
vec4 frame_sample(float frame, vec2 local_uv) {
	vec2 cell = vec2(mod(frame,4.0),floor(frame/4.0));
	return texture(volume_atlas,(clamp(local_uv,vec2(0.008),vec2(0.992))+cell)/4.0);
}
void fragment() {
    float frame = clamp(progress*15.0,0.0,15.0);
    vec4 dust = mix(frame_sample(floor(frame),UV),frame_sample(min(floor(frame)+1.0,15.0),UV),fract(frame));
    if (dust.a<0.01) discard;
    ALBEDO = dust.rgb;
    ALPHA = dust.a*effect_opacity*(1.0-smoothstep(0.65,1.0,progress));
}
