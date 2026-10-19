// Original thin annular shock-front shading on the authored library ring.
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never;
uniform vec4 primary_color : source_color = vec4(1.0,0.86,0.32,1.0);
uniform float emission = 2.0;
uniform float effect_opacity = 1.0;
instance uniform float progress = 0.0;
void fragment() {
	float band = pow(max(sin(UV.y * PI),0.0),1.5);
	ALBEDO = primary_color.rgb * (1.0+emission);
	EMISSION = primary_color.rgb * emission;
	ALPHA = band * (1.0-smoothstep(0.1,1.0,progress)) * effect_opacity;
}
