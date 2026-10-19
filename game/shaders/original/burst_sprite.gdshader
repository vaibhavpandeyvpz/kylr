// Original analytic gas, smoke and shock-front cards; no vendor atlases.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never;
uniform vec4 primary_color : source_color = vec4(1.0, 0.72, 0.25, 1.0);
uniform vec4 secondary_color : source_color = vec4(1.0, 0.16, 0.015, 1.0);
uniform vec4 tertiary_color : source_color = vec4(0.06, 0.055, 0.05, 1.0);
uniform float emission = 2.0;
uniform float effect_opacity = 1.0;
uniform float effect_emission = 1.0;
uniform int style = 0; // 0 hot gas, 1 smoke, 2 ring
uniform bool billboard = true;
uniform bool library_card = true;
uniform float card_width = 1.0;
uniform bool use_atlas = false;
uniform int flash_profile = -1;
uniform sampler2D gas_atlas : filter_linear_mipmap, repeat_disable;
instance uniform float progress = 0.0;
varying vec4 particle_color;
void vertex() {
	if (library_card) VERTEX = vec3(VERTEX.x,VERTEX.z-0.5,0.0);
	VERTEX.x *= card_width;
	particle_color = COLOR;
	if (billboard) {
		MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
		MODELVIEW_MATRIX[0].xyz *= length(MODEL_MATRIX[0].xyz);
		MODELVIEW_MATRIX[1].xyz *= length(MODEL_MATRIX[1].xyz);
		MODELVIEW_MATRIX[2].xyz *= length(MODEL_MATRIX[2].xyz);
	}
}
void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	float aa = max(fwidth(r), 0.005);
	float boundary = 0.85 + sin(p.x * 11.0 + p.y * 8.0) * 0.06 + sin(p.y * 19.0) * 0.035;
	float density = 1.0 - smoothstep(boundary - 0.25, boundary, r);
	if (style == 2) density = exp(-pow((r - 0.73) / max(0.045, aa), 2.0));
	float age = clamp(progress, 0.0, 1.0);
	if (flash_profile >= 0) {
		float along = clamp(1.0-UV.y,0.0,1.0);
		float across = abs(UV.x*2.0-1.0);
		float width = max(0.02,0.8*(1.0-along*0.6)*pow(sin(PI*along),0.45));
		density = 1.0-smoothstep(max(0.0,width-0.2),width,across);
		if (flash_profile == 1) {
			float core = exp(-pow(across/(0.15+along*0.1),2.0));
			float prongs = exp(-pow((across-along*0.55)/0.10,2.0))*0.65;
			density = max(core,prongs)*pow(1.0-along,0.5);
		}
		if (flash_profile == 2) {
			width = max(0.02,0.95*sin(PI*along));
			density = (1.0-smoothstep(width*0.65,width,across))*(0.45+0.55*abs(sin(UV.x*PI*3.0+along*1.3)));
		}
		if (flash_profile == 3) {
			width = 0.15+0.8*sqrt(along);
			density = exp(-pow(across/width,2.0)*3.0)*(1.0-smoothstep(0.5,1.0,along));
		}
		density *= smoothstep(0.0,0.08,along);
	}
	if (use_atlas) {
		float frame = min(floor(age*16.0),15.0);
		vec2 tile = vec2(mod(frame,4.0),floor(frame/4.0));
		density *= texture(gas_atlas,(clamp(UV,vec2(0.008),vec2(0.992))+tile)/4.0).a;
	}
	vec3 heat = mix(primary_color.rgb, secondary_color.rgb, smoothstep(0.0, 0.6, age));
	float fade = (1.0 - smoothstep(0.15, 1.0, age)) * particle_color.a;
	if (style == 1) {
		heat = tertiary_color.rgb;
		fade *= smoothstep(0.0, 0.12, age + 0.03) * 0.45;
	}
	ALBEDO = style == 1 ? heat : heat * (1.0 + emission * effect_emission);
	EMISSION = style == 1 ? vec3(0.0) : heat * emission * effect_emission;
	ALPHA = clamp(density * fade * effect_opacity, 0.0, 0.92);
}
