shader_type spatial;
render_mode unshaded, cull_disabled, blend_add, shadows_disabled;

instance uniform vec4 round_color : source_color = vec4(1.0, 0.62, 0.22, 1.0);
instance uniform float emission_energy : hint_range(0.0, 24.0) = 8.0;
instance uniform float opacity : hint_range(0.0, 1.0) = 1.0;
instance uniform float tail_layer : hint_range(0.0, 1.0) = 0.0;

void fragment() {
	float edge = 1.0 - abs(dot(normalize(NORMAL), normalize(VIEW)));
	float center = 1.0 - smoothstep(0.18, 0.92, edge);
	float along = UV.y;
	float tail_fade = mix(1.0, smoothstep(0.0, 0.95, 1.0 - along), tail_layer);
	float alpha = opacity * tail_fade * mix(0.86 + center * 0.14, 0.42 + center * 0.58, tail_layer);
	vec3 hot_color = mix(round_color.rgb, vec3(1.0, 0.96, 0.78), center * (1.0 - tail_layer * 0.58));
	ALBEDO = hot_color;
	EMISSION = hot_color * emission_energy * alpha;
	ALPHA = alpha;
}
