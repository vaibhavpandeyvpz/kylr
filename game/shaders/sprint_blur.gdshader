shader_type canvas_item;
uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_linear_mipmap;
uniform float intensity : hint_range(0.0, 1.0) = 0.0;
void fragment() {
	float edge = smoothstep(0.28, 0.7, length(UV - vec2(0.5)));
	vec3 sharp = textureLod(screen_texture, SCREEN_UV, 0.0).rgb;
	vec3 blur = textureLod(screen_texture, SCREEN_UV, 3.0).rgb;
	COLOR = vec4(mix(sharp, blur, edge * intensity), 1.0);
}
