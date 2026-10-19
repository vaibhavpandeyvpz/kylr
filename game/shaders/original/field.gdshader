// Original KYLR portal and capture-field surface. No texture dependencies.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;
uniform vec4 primary_color : source_color = vec4(0.4, 0.72, 1.0, 1.0);
uniform vec4 secondary_color : source_color = vec4(0.03, 0.13, 0.4, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.0, 0.02, 0.08, 1.0);
uniform float speed_scale = 1.0;
uniform bool circular = false;
uniform bool glow_only = false;
uniform vec2 size = vec2(1.0);
uniform sampler2D turbulence_texture : filter_linear_mipmap, repeat_enable;
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float radius = length(p);
	float border = circular ? 1.0 - radius : min(1.0 - abs(p.x), 1.0 - abs(p.y));
	float aa = max(fwidth(border), 0.002);
	float mask = smoothstep(0.0, aa * 2.0, border);
	float time = TIME * speed_scale;
	vec4 flow = texture(turbulence_texture,UV*vec2(2.0,3.0)+vec2(time*0.05,-time*0.08));
	vec2 displaced = UV + (flow.gb-0.5)*0.13;
	float cells = texture(turbulence_texture,displaced*vec2(3.0,5.0)-vec2(0,time*0.04)).r;
	float edge = exp(-max(border,0.0)*(7.0+cells*12.0));
	float interference = smoothstep(0.5,0.73,cells+flow.b*0.12);
	vec3 color = mix(secondary_color.rgb,primary_color.rgb,clamp(edge+interference*0.3,0.0,1.0));
	float strength = glow_only ? edge*0.2 : 0.36+edge*0.6+interference*edge*0.3;
	ALBEDO = color * (0.65+edge*4.0);
	EMISSION = color * (0.3+edge*3.0);
	ALPHA = mask * strength;
}
