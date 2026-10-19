shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never;
uniform float strength : hint_range(0.0, 1.0) = 0.0;
void vertex() {
	// The opaque depth comes from ray traversal in RT mode. A coplanar raster
	// overlay can alternate in front/behind it after depth conversion. Lift it
	// one millimetre while keeping depth testing against foreground cover.
	VERTEX += NORMAL * 0.001;
}
void fragment() {
	float rim = pow(1.0 - max(dot(normalize(NORMAL), normalize(VIEW)), 0.0), 2.0);
	ALBEDO = vec3(1.0, 0.82, 0.48);
	EMISSION = ALBEDO * strength * (0.8 + rim * 1.8);
	ALPHA = strength * (0.3 + rim * 0.35);
}
