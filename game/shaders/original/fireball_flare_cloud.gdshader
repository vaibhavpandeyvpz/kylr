// Folded three-dimensional fuel membranes, independently curling and eroding.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;
uniform sampler2D flow_material : filter_linear_mipmap, repeat_enable;
uniform sampler2D flow_relief : filter_linear_mipmap, repeat_enable;
uniform float phase = 0.0;
uniform bool flow_sheet = false;
uniform float flare_length = 0.48;
uniform float flare_radius = 0.16;
uniform float emission = 1.0;
uniform float effect_emission = 1.0;
uniform float effect_opacity = 1.0;
instance uniform float progress = 0.0;
varying float along;
varying vec2 flow_uv;
void vertex() {
	along = UV.y;
	float angle = (flow_sheet ? atan(VERTEX.y,VERTEX.x) : UV.x*TAU)+phase+progress*2.2;
	float width = pow(max(sin(along*PI),0.0),0.7)*(1.0-along*0.4);
	float folds = 1.0+0.22*sin(angle*3.0+along*9.0-progress*6.0)+0.12*cos(angle*5.0-along*7.0);
	float radius = flare_radius*width*folds;
	vec2 curl = vec2(sin(along*7.0+phase-progress*5.0),cos(along*5.0+phase-progress*4.0))*along*0.07;
	VERTEX = vec3(cos(angle)*radius+curl.x,along*flare_length,sin(angle)*radius+curl.y);
	NORMAL = normalize(vec3(cos(angle),0.15,sin(angle)));
	flow_uv = vec2(flow_sheet ? UV.x*0.15+phase : UV.x+phase,along-progress*1.2);
}
void fragment() {
	vec4 fuel = texture(flow_material,flow_uv);
	vec4 relief = texture(flow_relief,flow_uv);
	float erode = mix(0.15,0.72,smoothstep(0.25,1.0,progress));
	float filaments = smoothstep(erode,erode+0.24,fuel.a);
	float end_mask = smoothstep(0.0,0.08,along)*(1.0-smoothstep(0.72,1.0,along));
	float facing = pow(abs(dot(normalize(NORMAL),normalize(VIEW))),0.45);
	float fade = 1.0-smoothstep(0.35,1.0,progress);
	vec3 color = mix(vec3(0.65,0.012,0.001),fuel.rgb,0.65+fuel.a*0.25);
	float fold_light = 0.7+relief.b*0.3;
	ALBEDO = color*fold_light;
	EMISSION = color*emission*effect_emission*0.4;
	ROUGHNESS = relief.a;
	NORMAL_MAP = relief.rgb;
	NORMAL_MAP_DEPTH = 0.35;
	ALPHA = filaments*end_mask*fade*mix(0.15,0.75,facing)*effect_opacity;
}
