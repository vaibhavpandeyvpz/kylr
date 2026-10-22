// A closed ion shell with six scallops and three broken latitude bands.
shader_type spatial;
render_mode unshaded, blend_add, cull_back, depth_draw_never;
uniform vec4 primary_color : source_color = vec4(0.0,0.9,1.0,1.0);
uniform vec4 secondary_color : source_color = vec4(0.02,0.4,0.7,1.0);
uniform vec4 core_color : source_color = vec4(0.7,1.0,1.0,1.0);
uniform float emission_energy = 3.0;
uniform float effect_opacity = 1.0;
uniform float effect_progress = 0.0;
uniform int layer = 0;
varying vec3 surface_point;
void vertex() {
	surface_point = VERTEX;
	if (layer==1) {
		float flute = sin(atan(VERTEX.y,VERTEX.x)*6.0+VERTEX.z*9.0);
		VERTEX += NORMAL*flute*0.025*sin(effect_progress*PI);
	}
}
void fragment() {
	float p = effect_progress;
	vec3 q = normalize(surface_point+vec3(0.00001));
	float facing = abs(dot(normalize(NORMAL),normalize(VIEW)));
	float rim = pow(1.0-facing,1.6);
	float longitude = atan(q.y,q.x);
	float cells = sin(q.x*21.0+p*4.0)*sin(q.y*19.0-p*3.0)*sin(q.z*23.0);
	float seams = 1.0-smoothstep(0.03,0.19,abs(cells));
	float fade = 1.0-smoothstep(0.38,1.0,p);
	float mask = layer==0 ? pow(facing,0.5) : (layer==3 ? 0.8 : (0.12+0.46*rim+0.42*seams));
	if (layer==2) {
		float bands = pow(max(0.0,cos(q.z*15.0-p*3.0)),16.0);
		float gaps = smoothstep(-0.25,0.35,sin(longitude*6.0+p*2.0));
		mask = bands*gaps*0.65;
	}
	vec3 tint = mix(secondary_color.rgb,primary_color.rgb,clamp(rim+seams*0.7,0.0,1.0));
	if (layer==0 || layer==3) tint = core_color.rgb;
	ALBEDO = tint*emission_energy;
	EMISSION = tint*emission_energy;
	ALPHA = mask*fade*effect_opacity;
}
