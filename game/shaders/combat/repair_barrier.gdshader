shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled;
uniform vec4 tint : source_color = vec4(0.376,0.937,0.596,1.0);
uniform bool motion_enabled = true;

void fragment() {
	// The native cylindrical/domed UV is continuous around U; 32 columns close
	// at its seam. Fade the grid near the pole to avoid converging bright lines.
	vec2 p=UV*vec2(32.0,16.5);
	vec2 period=vec2(1.0,1.7320508);
	vec2 a=mod(p,period)-period*0.5;
	vec2 b=mod(p-period*0.5,period)-period*0.5;
	vec2 cell=dot(a,a)<dot(b,b) ? a : b;
	vec2 q=abs(cell);
	float distance_to_center=max(q.x,dot(q,vec2(0.5,0.8660254)));
	float aa=max(fwidth(distance_to_center),0.001);
	float grid=(1.0-smoothstep(0.012-aa,0.012+aa,0.5-distance_to_center));
	grid*=1.0-smoothstep(0.85,0.97,UV.y);
	float clock=motion_enabled ? TIME : 0.0;
	float scan_height=fract(clock*0.16);
	float scan=exp(-pow((UV.y-scan_height)/0.024,2.0))*sin(scan_height*3.14159265);
	float rim=pow(1.0-abs(dot(normalize(NORMAL),normalize(VIEW))),3.0);
	float floor_ring=1.0-smoothstep(0.008,0.022,UV.y);
	ALBEDO=tint.rgb*0.35;
	EMISSION=tint.rgb*(grid*0.7+scan*0.55+rim*0.25+floor_ring*1.2);
	ALPHA=clamp(0.014+grid*0.055+scan*0.045+rim*0.08+floor_ring*0.12,0.0,0.24);
}
