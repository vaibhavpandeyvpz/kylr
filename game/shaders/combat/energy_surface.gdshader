shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back;
uniform vec4 tint : source_color = vec4(0.3,1.0,0.5,1.0);
uniform vec4 hit_tint : source_color = vec4(1.0,0.85,0.2,1.0);
uniform float surface_offset = 0.05;
uniform float shield_strength = 0.0;
uniform float hit_strength = 0.0;
uniform bool motion_enabled = true;
varying vec3 surface_position;

void vertex() {
	surface_position=VERTEX;
	VERTEX+=NORMAL*surface_offset;
}

void fragment() {
	float clock=motion_enabled ? TIME : 0.0;
	// A continuous 3D field wraps all native parts without UV seams or a new mesh.
	vec3 p=surface_position*18.0;
	float turn=clock*0.35;
	p.xz=mat2(vec2(cos(turn),sin(turn)),vec2(-sin(turn),cos(turn)))*p.xz;
	p+=vec3(clock*0.6,-clock*1.7,clock*0.4);
	vec3 warp=sin(p.yzx*0.51+sin(p.zxy*0.37))*1.7;
	float vein=abs(sin(p.x+warp.x+sin(p.y*0.63+warp.y))*sin(p.z*0.8+warp.z));
	float filaments=1.0-smoothstep(0.025,0.12,vein);
	float sparks=pow(max(0.0,sin(dot(p,vec3(1.3,0.7,1.1))+warp.y)),16.0)*filaments;
	float rim=pow(1.0-clamp(dot(normalize(NORMAL),normalize(VIEW)),0.0,1.0),2.0);
	float active=max(shield_strength,hit_strength);
	vec3 color=mix(tint.rgb,hit_tint.rgb,clamp(hit_strength*2.0,0.0,1.0));
	float energy=filaments*(0.8+sparks*0.8)+rim*0.04;
	ALBEDO=color;
	EMISSION=color*(0.7+energy*2.0);
	ALPHA=clamp((energy*0.65+hit_strength*0.025)*active,0.0,0.9);
}
