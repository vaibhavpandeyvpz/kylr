shader_type spatial;
render_mode diffuse_burley;
uniform bool volcanic_surface = false;
uniform bool local_surface = false;
varying vec3 surface_local;
varying vec3 normal_local;

uniform sampler2D weights0 : filter_linear, repeat_disable;
uniform sampler2D weights1 : filter_linear, repeat_disable;
uniform sampler2D dust_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dust_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D basalt_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D basalt_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bedrock_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bedrock_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rubble_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rubble_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D compacted_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D compacted_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D scorch_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D scorch_normal : filter_linear_mipmap_anisotropic, repeat_enable;
varying vec3 terrain_world;
varying vec3 terrain_normal;

void vertex() {
	surface_local=VERTEX;
	normal_local=NORMAL;
	terrain_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	terrain_normal = mat3(MODEL_MATRIX) * NORMAL;
}

void layer(sampler2D color_map, sampler2D normal_map_tex, vec2 uv, float weight,
		inout vec4 color_sum, inout vec4 normal_sum) {
	if (weight > 0.005) {
		vec4 color = texture(color_map, uv);
		float blend = weight * mix(0.6, 1.4, color.a);
		color_sum += vec4(color.rgb, 1.0) * blend;
		normal_sum += texture(normal_map_tex, uv) * blend;
	}
}

void fragment() {
	vec2 control_uv = (terrain_world.xz + vec2(256.5)) / 512.0;
	vec3 first = texture(weights0, control_uv).rgb;
	vec3 second = texture(weights1, control_uv).rgb;
	vec3 facing = abs(normalize(local_surface?normal_local:terrain_normal));
	if(local_surface) { first=vec3(.48,.3,.12);second=vec3(.1,0.0,0.0); }
	if(volcanic_surface) {
		float rock=(1.0-smoothstep(.35,.85,facing.y))*.85;
		first=mix(first,vec3(0.0,.4,.6),rock);second*=1.0-rock;
	}
	vec3 coordinates=local_surface?surface_local:terrain_world;
	vec2 projection = facing.y >= max(facing.x, facing.z) ? coordinates.xz :
		(facing.x > facing.z ? coordinates.zy : coordinates.xy);
	vec2 uv = projection * 0.25;
	vec4 colors = vec4(0.0);
	vec4 normals = vec4(0.0);
	layer(dust_albedo, dust_normal, uv, first.r, colors, normals);
	layer(basalt_albedo, basalt_normal, uv, first.g, colors, normals);
	layer(bedrock_albedo, bedrock_normal, uv, first.b, colors, normals);
	layer(rubble_albedo, rubble_normal, uv, second.r, colors, normals);
	layer(compacted_albedo, compacted_normal, uv, second.g, colors, normals);
	layer(scorch_albedo, scorch_normal, uv, second.b, colors, normals);
	float total = max(colors.a, 0.001);
	ALBEDO = colors.rgb / total;
	NORMAL_MAP = normalize(normals.rgb / total * 2.0 - 1.0) * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = 0.7 * smoothstep(0.3, 0.85, facing.y);
	ROUGHNESS = clamp(normals.a / total, 0.65, 1.0);
	METALLIC = 0.0;
	SPECULAR = 0.0;
}
