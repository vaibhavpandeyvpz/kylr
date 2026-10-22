// Ray-integrated gas within closed, tapered library mesh envelopes. Axis +Y.
shader_type spatial;
render_mode unshaded, blend_mix, cull_front, depth_draw_never, depth_test_disabled;
uniform sampler3D density_volume : filter_linear, repeat_enable;
uniform sampler2D flow_material : filter_linear_mipmap, repeat_enable;
uniform sampler2D flow_relief : filter_linear_mipmap, repeat_enable;
uniform sampler2D scene_depth : hint_depth_texture, filter_nearest, repeat_disable;
uniform float beam_length = 1.0;
uniform float segment_length = 1.0;
uniform float full_damage_range = 8.0;
uniform float maximum_range = 10.0;
uniform float start_radius = 0.035;
uniform float end_radius = 0.17;
uniform float emission = 1.5;
uniform float effect_emission = 1.0;
uniform float effect_opacity = 1.0;
uniform float speed_scale = 1.0;
uniform int layer = 0;
uniform float flare_phase = 0.0;
uniform bool clip_enabled = false;
uniform bool robot_contact = false;
uniform vec3 clip_origin;
uniform vec3 clip_direction;
uniform float clip_length = 1.0;
uniform int march_steps = 24;
varying vec3 proxy_point;
varying vec3 camera_local;
void vertex() {
	float t = UV.y;
	float angle = UV.x*TAU;
	float cap = step(0.001,t)*step(t,0.999);
	float axial = clamp((t-1.0/12.0)/(10.0/12.0),0.0,1.0);
	float bound = max(start_radius,end_radius)*(layer>=3 ? 1.8 : 1.02);
	float along = layer==4 ? mix(0.8,1.0,axial) : axial;
	VERTEX = vec3(cos(angle)*bound*cap,along*beam_length,sin(angle)*bound*cap);
	proxy_point = VERTEX;
	camera_local = (inverse(MODEL_MATRIX)*INV_VIEW_MATRIX[3]).xyz;
}
void fragment() {
	vec3 direction = normalize(proxy_point-camera_local);
	float radius = max(start_radius,end_radius)*(layer>=3 ? 1.75 : 1.0);
	float a = dot(direction.xz,direction.xz);
	float b = dot(camera_local.xz,direction.xz);
	float c = dot(camera_local.xz,camera_local.xz)-radius*radius;
	float discriminant = b*b-a*c;
	if (discriminant<0.0 || (a<0.000001 && c>0.0)) discard;
	float begin = 0.0;
	float end = 10000.0;
	if (a>0.000001) {
		float root = sqrt(max(0.0,discriminant));
		begin = max(0.0,(-b-root)/a);
		end = (-b+root)/a;
	}
	if (abs(direction.y)>0.000001) {
		float low = ((layer==4 ? beam_length*0.8 : 0.0)-camera_local.y)/direction.y;
		float high = (beam_length-camera_local.y)/direction.y;
		begin = max(begin,min(low,high));
		end = min(end,max(low,high));
	} else if (camera_local.y<0.0 || camera_local.y>beam_length) { discard; }
	float depth = texture(scene_depth,SCREEN_UV).r;
	if (depth>0.000001) {
		vec4 view_point = INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,depth,1.0);
		view_point /= view_point.w;
		vec3 obstacle = (inverse(MODEL_MATRIX)*INV_VIEW_MATRIX*view_point).xyz;
		end = min(end,dot(obstacle-camera_local,direction));
	}
	if (end<=begin) discard;
	float step_size = (end-begin)/float(march_steps);
	vec3 color_sum = vec3(0.0);
	float alpha = 0.0;
	float time = TIME*speed_scale;
	for (int i=0;i<32;i++) {
		if (i>=march_steps || alpha>0.98) break;
		vec3 p = camera_local+direction*(begin+(float(i)+0.5)*step_size);
		float t = clamp(p.y/beam_length,0.0,1.0);
		float angle = atan(p.z,p.x)/TAU;
		vec3 noise_point = vec3(p.x*9.0,(p.y-time*6.0)*1.7,p.z*9.0)+float(layer)*0.317;
		float coarse = texture(density_volume,noise_point*0.55).r;
		float fine = texture(density_volume,noise_point*1.83+vec3(0.3,0.7,0.1)).r;
		vec4 flow = textureLod(flow_material,vec2(angle,(p.y-time*6.0)*0.8),2.0);
		vec4 relief = textureLod(flow_relief,vec2(angle,(p.y-time*6.0)*0.8),2.0);
		float local_radius = mix(start_radius,end_radius,sqrt(t));
		vec2 swirl = vec2(sin(p.y*4.0-time*3.0),cos(p.y*3.3-time*2.5))*local_radius*0.13*t;
		if (layer>=3) {
			float flare_t = layer==4 ? clamp((t-0.8)/0.2,0.0,1.0) : t;
			float opening = smoothstep(0.0,0.12,flare_t);
			float flow_along = p.y-time*6.0;
			float flare_angle = flare_phase+flow_along*0.6+sin(flow_along*2.0)*0.6;
			float billow = pow(max(sin(flare_t*PI),0.0),0.65);
			local_radius = (0.04+0.09*billow)*(0.7+coarse*0.6)*opening*0.5+0.003;
			if (layer==4) local_radius *= 0.85;
			float segment_t = clamp(p.y/segment_length,0.0,1.0);
			float main_radius = mix(0.05,end_radius,sqrt(segment_t));
			float orbit = max(0.0,main_radius*0.78-local_radius*0.15)*opening;
			swirl = vec2(sin(p.y*4.0-time*3.0),cos(p.y*3.3-time*2.5))*main_radius*0.13*segment_t;
			swirl += vec2(cos(flare_angle),sin(flare_angle))*orbit;
		}
		float radial = length(p.xz-swirl)/max(local_radius,0.001);
		float edge = 0.65+coarse*0.35;
		float envelope = 1.0-smoothstep(edge-0.28,edge,radial);
		float structure = smoothstep(0.18,0.65,coarse*0.6+fine*0.25+flow.a*0.15);
		float density = envelope*structure;
		if (layer==1) density *= mix(1.0,0.15+0.85*smoothstep(0.2,0.7,fine),smoothstep(0.72,0.97,t));
		float heat = clamp(0.45-t*0.25+coarse*0.8-radial*0.24,0.0,1.0);
		if (layer==0) { density *= 0.45; heat = 0.8+coarse*0.15-radial*0.24; }
		if (layer==2) { density *= smoothstep(0.25,0.75,radial)*0.25; heat *= 0.6; }
		if (layer>=3) {
			float tongues = smoothstep(0.25,0.75,0.5+0.5*sin((p.y-time*6.0)*3.5+flare_phase+coarse*3.0));
			density *= tongues*0.45;
			heat = clamp(heat+0.18,0.0,0.9);
			if (layer==4) {
				density *= smoothstep(0.8,0.84,t);
			}
		}
		float tip_fade = smoothstep(0.01,0.14,beam_length-p.y);
		if (robot_contact && (layer==1 || layer==2 || layer==4)) tip_fade = 1.0;
		float range_fade = 1.0-smoothstep(full_damage_range,maximum_range,p.y);
		density *= tip_fade*range_fade*effect_opacity;
		vec3 world_point = (MODEL_MATRIX*vec4(p,1.0)).xyz;
		if (clip_enabled && dot(world_point-clip_origin,clip_direction)>clip_length) density = 0.0;
		vec3 color = mix(vec3(0.75,0.035,0.002),vec3(1.0,0.28,0.012),smoothstep(0.3,0.75,heat));
		color = mix(color,vec3(1.0,0.82,0.36),smoothstep(0.8,1.0,heat));
		color *= 0.85+relief.b*0.15;
		float opacity = 1.0-exp(-density*step_size*18.0/max(local_radius*4.0,0.05));
		float weight = (1.0-alpha)*opacity;
		color_sum += color*(1.0+heat*emission*effect_emission)*weight;
		alpha += weight;
	}
	if (alpha<0.005) discard;
	ALBEDO = color_sum/max(alpha,0.001);
	ALPHA = alpha;
}
