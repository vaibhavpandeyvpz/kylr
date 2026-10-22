shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never;

uniform sampler2D turbulence : filter_linear_mipmap, repeat_enable;
uniform sampler2D gas_atlas : filter_linear_mipmap, repeat_disable;
uniform sampler2D flow_material : filter_linear_mipmap, repeat_enable;
uniform sampler2D flow_relief : filter_linear_mipmap, repeat_enable;
uniform vec4 outer_color : source_color = vec4(1.0,0.63,0.1,1.0);
uniform vec4 jet_color : source_color = vec4(1.0,0.97,0.78,1.0);
uniform vec4 edge_color : source_color = vec4(1.0,0.2,0.02,1.0);
uniform float emission = 5.5;
uniform float effect_emission = 1.0;
uniform float effect_opacity = 1.0;
uniform float outer_radius = 0.075;
uniform float outer_length = 0.105;
uniform float jet_radius = 0.024;
uniform float jet_length = 0.42;
uniform float layer_scale = 1.0;
uniform bool open_rim = false;
uniform bool flow_sheet = false;
uniform int profile = 0;
uniform bool core_layer = false;
uniform float layer_energy = 1.0;
instance uniform float progress = 0.0;
instance uniform float shot_phase = 0.0;
varying vec3 flare_point;
varying vec2 gas_uv;
varying float flare_along;

void vertex() {
    float front_radius = core_layer ? jet_radius : outer_radius;
    float length_m = core_layer ? jet_length : outer_length;
    float width_variation = 0.88+0.24*(0.5+0.5*sin(shot_phase*1.79));
    float length_variation = 0.87+0.13*(0.5+0.5*sin(shot_phase*2.37));
    float angle = flow_sheet ? atan(VERTEX.y,VERTEX.x) : UV.x*TAU;
    angle += shot_phase*0.37;
    float along = open_rim ? 0.94+0.025*sin(angle*3.0+shot_phase) : UV.y;
    float lobes = 1.0+0.18*sin(angle*3.0+shot_phase+along*2.0)
        +0.11*sin(angle*5.0-shot_phase*0.73-along*4.0)
        +0.07*sin(angle*9.0+shot_phase*1.31);
    float body = core_layer ? pow(max(sin(PI*clamp(along,0.0,1.0)),0.0),0.7)*(1.0-along*0.65)
        : pow(clamp(along,0.0,1.0),0.7);
    float radius = 0.004+front_radius*body;
    if (profile==1) radius *= 0.83+0.17*abs(sin(angle*1.5+shot_phase));
    if (profile==2) radius *= 0.9+0.1*sin(angle*2.0+along*5.0+shot_phase);
    if (open_rim) {
        float rim_radius = front_radius*(0.8+UV.y*0.2)*lobes*width_variation;
        VERTEX = vec3(along*length_m,cos(angle)*rim_radius,sin(angle)*rim_radius);
        gas_uv = VERTEX.yz/max(front_radius*2.4,0.01)+vec2(0.5);
    } else {
        VERTEX = vec3(along*length_m,cos(angle)*radius*lobes*width_variation,sin(angle)*radius*lobes*width_variation);
        gas_uv = vec2(UV.x,UV.y*0.7+0.15);
    }
    float growth = mix(0.22,1.0,smoothstep(0.0,0.32,progress));
    VERTEX *= vec3(length_variation*growth,layer_scale,layer_scale);
    NORMAL = open_rim ? vec3(1.0,0.0,0.0)
        : normalize(vec3(core_layer ? (along-0.3)*0.9 : -0.3,cos(angle),sin(angle)));
    flare_point = VERTEX;
    flare_along = along;
}

void fragment() {
    float along = clamp(flare_along,0.0,1.0);
    float angle = atan(flare_point.z,flare_point.y);
    vec2 flow_uv = vec2(angle/TAU+shot_phase*0.13,along*1.7-progress*0.8);
    vec4 noise = texture(turbulence,flow_uv);
    vec2 material_uv = vec2(angle/TAU+shot_phase*0.17,along*0.85-progress*0.6);
    material_uv += (noise.rg-vec2(0.5))*0.07;
    vec4 flow = texture(flow_material,material_uv);
    vec4 relief = texture(flow_relief,material_uv);
    float frame = min(floor(progress*10.0),9.0);
    vec2 tile = vec2(mod(frame,4.0),floor(frame/4.0));
    float texture_density = texture(gas_atlas,(clamp(gas_uv,vec2(0.008),vec2(0.992))+tile)/4.0).a;
    float ragged = smoothstep(0.12+progress*0.35,0.7,flow.a*0.82+noise.r*0.18);
    float tip = core_layer ? 1.0-smoothstep(0.68+noise.b*0.2,1.0,along)
        : 1.0-smoothstep(0.7+noise.b*0.15,1.0,along);
    float density = ragged*(open_rim ? mix(0.25,0.8,texture_density) : tip);
    if (flow_sheet) density *= pow(max(sin(PI*UV.x),0.0),0.65);
    if (open_rim) density *= max(sin(PI*UV.y),0.0);
    density *= smoothstep(0.02,0.48,abs(dot(normalize(NORMAL),normalize(VIEW))));
    float pulse = 1.0-smoothstep(0.18,0.7,progress);
    float fade = pow(max(1.0-progress,0.0),0.8);
    vec3 heat = mix(outer_color.rgb,edge_color.rgb,smoothstep(0.45,1.0,along)*0.65+progress*0.15);
    heat = mix(heat,jet_color.rgb,core_layer ? 0.95 : open_rim ? 0.5 : smoothstep(0.8,1.0,flow.a)*0.12);
    float filament = mix(0.75,1.15,flow.a)*mix(0.9,1.05,relief.b)*mix(1.0,0.95,relief.a);
    ALBEDO = heat;
    EMISSION = heat*emission*effect_emission*(0.25+0.75*pulse)*layer_energy*filament;
    ALPHA = density*fade*(0.3+0.7*pulse)*effect_opacity*(open_rim ? 0.45 : 0.75);
}
