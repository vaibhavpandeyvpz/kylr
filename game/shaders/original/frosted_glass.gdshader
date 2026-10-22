// Original thin dielectric approximation for KYLR's authored glass surfaces.
// Screen transmission samples the opaque scene color.
shader_type spatial;
render_mode blend_mix, cull_back, depth_draw_never;
uniform sampler2D opaque_color : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform vec4 color : source_color = vec4(0.8,0.9,1.0,0.25);
uniform float opacity : hint_range(0.0,1.0) = 0.25;
uniform float refraction_strength : hint_range(0.0,0.03) = 0.008;
uniform float blur_amount : hint_range(0.0,5.0) = 1.5;
uniform float roughness : hint_range(0.0,1.0) = 0.12;
void fragment() {
	vec3 normal = normalize(NORMAL);
	float facing = clamp(abs(dot(normal,normalize(VIEW))),0.0,1.0);
	float fresnel = 0.04+0.96*pow(1.0-facing,5.0);
	vec2 offset = normal.xy * refraction_strength * (1.0-facing*0.6);
	vec2 uv = clamp(SCREEN_UV+offset,vec2(0.001),vec2(0.999));
	vec3 transmitted = textureLod(opaque_color,uv,blur_amount).rgb;
	vec3 absorption = mix(vec3(1.0),color.rgb,clamp(opacity*1.4,0.0,1.0));
	ALBEDO = color.rgb * 0.08;
	EMISSION = transmitted * absorption * (1.0-fresnel*0.5);
	METALLIC = 0.0;
	SPECULAR = 0.5;
	ROUGHNESS = roughness;
	ALPHA = clamp(opacity+fresnel*(1.0-opacity)*0.55,0.0,1.0);
}
