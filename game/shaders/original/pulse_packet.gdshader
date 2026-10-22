// Reuse the authored packet topology as a capped, constant-diameter tracer.
shader_type spatial;
render_mode unshaded, blend_add, cull_back, depth_draw_never;
instance uniform float core_layer = 0.0;
instance uniform float length_m = 0.0;
void vertex() {
	float angle = -UV.x*TAU;
	float radius = mix(0.025,0.009,core_layer);
	float axial = clamp((UV.y-0.125)/0.75,0.0,1.0);
	float cap = step(0.001,UV.y)*step(UV.y,0.999);
	vec3 radial = vec3(cos(angle),sin(angle),0.0);
	VERTEX = radial*radius*cap+vec3(0.0,0.0,axial*length_m);
	NORMAL = UV.y<=0.125 ? vec3(0.0,0.0,-1.0) : (UV.y>=0.875 ? vec3(0.0,0.0,1.0) : radial);
}
void fragment() {
	float facing = abs(dot(normalize(NORMAL),normalize(VIEW)));
	vec3 tint = mix(vec3(0.0,0.85,1.0),vec3(0.28,0.95,1.0),core_layer);
	ALBEDO = tint*mix(2.5,4.0,core_layer);
	EMISSION = tint*mix(3.0,5.0,core_layer);
	ALPHA = mix(0.55*pow(facing,0.65),0.9,core_layer);
}
