// Original layered gas shell; independently generated library noise and meshes.
shader_type spatial;
render_mode unshaded, blend_mix, cull_back, depth_draw_never;
uniform sampler2D turbulence : filter_linear_mipmap, repeat_enable;
uniform vec4 primary_color : source_color = vec4(1.0,0.86,0.32,1.0);
uniform vec4 secondary_color : source_color = vec4(1.0,0.19,0.008,1.0);
uniform vec4 tertiary_color : source_color = vec4(0.18,0.15,0.12,1.0);
uniform float emission = 4.5;
uniform float effect_opacity = 1.0;
uniform float effect_emission = 1.0;
uniform bool smoke = false;
uniform float phase = 0.0;
instance uniform float progress = 0.0;
void fragment() {
	vec2 uv = UV * vec2(3.0,2.5) + vec2(phase,-progress*0.65);
	vec4 flow = texture(turbulence,uv);
	float shape = texture(turbulence,uv + (flow.gb-0.5)*0.23).r;
	float threshold = mix(0.46,0.78,progress);
	float aa = max(fwidth(shape),0.18);
	float coverage = smoothstep(threshold-aa,threshold+aa,shape);
	float cooling = smoothstep(0.08,0.75,progress);
	float facing = clamp(abs(dot(normalize(NORMAL),normalize(VIEW))),0.0,1.0);
	float hot = clamp((shape-0.3)*1.8,0.0,1.0) * (1.0-cooling);
	vec3 heat = mix(secondary_color.rgb,primary_color.rgb,hot*hot*(0.25+facing*0.75));
	if (smoke) heat = tertiary_color.rgb * (0.5+flow.r*0.7);
	ALBEDO = heat;
	EMISSION = smoke ? vec3(0.0) : heat * emission * effect_emission;
	float fade = 1.0-smoothstep(0.5,1.0,progress);
	ALPHA = coverage * fade * smoothstep(0.02,0.5,facing) * effect_opacity * (smoke ? 0.5 : 0.9);
}
