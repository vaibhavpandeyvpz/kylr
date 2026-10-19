shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, blend_add, shadows_disabled;

uniform vec4 primary_color : source_color = vec4(0.78, 0.66, 1.0, 1.0);
uniform vec4 secondary_color : source_color = vec4(0.95, 0.9, 1.0, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.12, 0.035, 0.28, 1.0);
uniform float emission_energy : hint_range(0.0, 12.0) = 4.5;
uniform float animation_speed : hint_range(0.0, 10.0) = 1.0;
uniform vec2 noise_scale = vec2(4.0, 2.0);
uniform vec2 noise_scroll = vec2(0.42, -0.18);
uniform float deformation : hint_range(0.0, 0.5) = 0.1;
// Distance fade belongs to the presentation; the swept hit volume is separate.
uniform float opacity : hint_range(0.0, 1.0) = 1.0;
uniform float shell_opacity : hint_range(0.0, 1.0) = 0.34;
uniform float edge_power : hint_range(0.25, 8.0) = 2.0;

varying vec3 local_position;
varying float surface_noise;

float charge_noise(vec3 position, float time) {
	float longitudinal = sin(position.y * noise_scale.y * 8.0 - time * noise_scroll.y * 6.0);
	float diagonal = sin(dot(position, vec3(11.0, 7.0, 13.0)) + time * noise_scroll.x * 5.0);
	float stepping = sin((abs(position.x) + abs(position.z)) * noise_scale.x * 8.0 - time * 3.2);
	return longitudinal * 0.46 + diagonal * 0.32 + stepping * 0.22;
}

void vertex() {
	float time = TIME * animation_speed;
	vec3 direction = normalize(VERTEX + vec3(0.0001));
	surface_noise = charge_noise(VERTEX, time);
	VERTEX += direction * length(VERTEX) * surface_noise * deformation;
	local_position = VERTEX;
}

void fragment() {
	float time = TIME * animation_speed;
	float noise = charge_noise(local_position, time);
	float facing = abs(dot(normalize(NORMAL), normalize(VIEW)));
	float rim = pow(1.0 - facing, edge_power);
	float bands = smoothstep(0.16, 0.86, sin(local_position.y * 36.0 - time * 10.0 + noise * 3.5) * 0.5 + 0.5);
	float winding = sin(atan(local_position.z,local_position.x)*3.0 + local_position.y*18.0 - time*8.0);
	float filament = 1.0-smoothstep(0.02,max(fwidth(winding),0.04)+0.12,abs(winding));
	float energy = clamp(rim*0.2+filament*0.7+bands*0.1,0.0,1.0);
	vec3 tint = mix(tertiary_color.rgb, primary_color.rgb, smoothstep(0.04, 0.7, energy));
	tint = mix(tint, secondary_color.rgb, bands * rim * 0.58);
	ALBEDO = tint;
	EMISSION = tint * emission_energy * (0.05+filament*0.8+rim*0.3);
	ALPHA = opacity * shell_opacity * (rim*0.18+filament*0.5);
}
