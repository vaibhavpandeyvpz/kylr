// Hot, tumbling metal rather than a spherical energy projectile.
shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_never;
instance uniform vec4 round_color : source_color = vec4(1.0,0.62,0.22,1.0);
instance uniform float emission_energy = 2.8;
instance uniform float opacity = 1.0;
void vertex() {
	float angle = TIME*11.0;
	mat3 tumble = mat3(vec3(cos(angle),0.0,-sin(angle)),vec3(0.0,1.0,0.0),vec3(sin(angle),0.0,cos(angle)));
	VERTEX = tumble*VERTEX;
	NORMAL = tumble*NORMAL;
}
void fragment() {
	float edge = pow(1.0-abs(dot(normalize(NORMAL),normalize(VIEW))),2.0);
	ALBEDO = vec3(0.08,0.07,0.06);
	METALLIC = 0.65;
	ROUGHNESS = 0.62;
	EMISSION = round_color.rgb*emission_energy*(0.12+edge*0.4);
	ALPHA = opacity;
}
