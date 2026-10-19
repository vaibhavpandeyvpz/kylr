// Fleeting broken ionization front, distinct from the neutral EMP volume.
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never;
uniform vec4 primary_color : source_color = vec4(0.4,0.85,1.0,1.0);
uniform float effect_opacity = 1.0;
instance uniform float progress = 0.0;
void fragment() {
	float band = pow(max(sin(UV.y*PI),0.0),3.0);
	float broken = smoothstep(0.15,0.65,sin(UV.x*TAU*5.0+progress*7.0));
	ALBEDO = primary_color.rgb;
	EMISSION = primary_color.rgb*0.6;
	ALPHA = band*broken*0.25*(1.0-smoothstep(0.05,0.4,progress))*effect_opacity;
}
