// Original seeded abrasion, a dark impact cavity and fine radial fractures.
shader_type spatial;
render_mode unshaded, cull_disabled, blend_mix, depth_draw_never;
// Keep the existing 64-variant instance API used by pooled surface marks.
instance uniform int atlas_cell : hint_range(0, 63, 1) = 0;
instance uniform float progress = 0.0;
uniform float opacity : hint_range(0.0,1.0) = 1.0;

float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float grain(vec2 p) {
	vec2 cell = floor(p), q = fract(p);
	q = q*q*(3.0-2.0*q);
	return mix(mix(hash(cell),hash(cell+vec2(1,0)),q.x),mix(hash(cell+vec2(0,1)),hash(cell+vec2(1)),q.x),q.y);
}
void fragment() {
	float seed = float(atlas_cell)*13.71;
	vec2 p = UV*2.0-1.0;
	float radius = length(p);
	float noise = grain(p*9.0+seed)*0.7+grain(p*27.0-seed)*0.3;
	float aa = max(fwidth(radius),0.006);
	float cavity_radius = 0.18+noise*0.09;
	float cavity = 1.0-smoothstep(cavity_radius-aa,cavity_radius+aa,radius);
	float chip = (1.0-smoothstep(0.3,0.48,radius+(noise-0.5)*0.18))*smoothstep(0.24,0.62,noise);
	float fractures = 0.0;
	for (int index=0;index<6;index++) {
		float id = float(index);
		float angle = id*TAU/6.0+hash(vec2(seed,id))*0.8;
		vec2 axis = vec2(cos(angle),sin(angle));
		float along = dot(p,axis);
		float across = abs(dot(p,vec2(-axis.y,axis.x))+(noise-0.5)*0.035);
		float reach = 0.35+hash(vec2(id,seed))*0.4;
		float line = 1.0-smoothstep(0.003,0.003+aa,across);
		fractures = max(fractures,line*smoothstep(0.15,0.24,along)*(1.0-smoothstep(reach-0.1,reach,along)));
	}
	float dust = (1.0-smoothstep(0.2,0.7,radius))*noise*0.16;
	ALBEDO = mix(vec3(0.09,0.075,0.06),vec3(0.008),cavity);
	ROUGHNESS = 1.0;
	ALPHA = max(cavity*0.92,max(chip*0.5,max(fractures*0.72,dust)))*opacity*(1.0-smoothstep(0.9,1.0,progress));
}
