shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;
uniform vec4 tint : source_color = vec4(0.2,0.8,1.0,1.0);
uniform float hit_progress = 1.0;
uniform vec3 hit_direction = vec3(0.0, 0.0, -1.0);
varying vec3 shell_position;
void vertex() {
	shell_position = VERTEX;
	// Millimetres of breathing on the baked nominal five-centimetre wrapper.
	float breath = sin(dot(VERTEX,vec3(7.0,5.0,4.0))-TIME*1.4);
	VERTEX += NORMAL * breath * 0.003;
}
void fragment() {
	vec3 p = shell_position;
	float a = dot(p,vec3(8.0,6.0,5.0))-TIME*0.8;
	float b = dot(p,vec3(-5.0,9.0,7.0))+TIME*0.55;
	float pools = smoothstep(0.45,0.95,sin(a+sin(b)*1.2));
	float rim = pow(1.0-clamp(dot(normalize(NORMAL),normalize(VIEW)),0.0,1.0),2.5);
	float distance_to_hit = length(normalize(p-vec3(0.0,0.95,0.0))-hit_direction);
	float ripple = (1.0 - smoothstep(0.035, 0.12, abs(distance_to_hit - hit_progress * 2.2))) * pow(1.0 - hit_progress, 1.5);
	ALBEDO = mix(tint.rgb,vec3(0.65,0.9,1.0),pools*0.25);
	ROUGHNESS = 0.09+(1.0-pools)*0.12;
	METALLIC = 0.12;
	SPECULAR = 0.85;
	EMISSION = tint.rgb*(0.12+rim*0.35+pools*0.12+ripple*2.0);
	ALPHA = 0.08+rim*0.28+pools*0.1+ripple*0.55;
}
