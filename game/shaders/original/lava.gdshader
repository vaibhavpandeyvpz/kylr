shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

// The lake surface's analytic swells and derivatives become slow viscous folds.
// Opaque basalt replaces water absorption, refraction, foam and caustics.
uniform sampler2D molten_basalt : source_color, filter_linear_mipmap, repeat_enable;
uniform float clock_seconds = 0.0;
uniform int detail = 2;
uniform vec2 flow_direction = vec2(0.8, 0.6);
uniform vec2 bubble_center = vec2(10000.0);
uniform float bubble_phase = -1.0;
uniform float bubble_radius = 0.05;
varying vec3 world_surface;

float hash(vec2 p) {
    vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.11369, 0.13787));
    q += dot(q, q.yzx + 19.19);
    return fract((q.x + q.y) * q.z);
}

float noise(vec2 p) {
    vec2 i=floor(p),f=fract(p),u=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),u.x),
               mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0)),u.x),u.y);
}

vec3 swell(vec2 p,vec2 direction,float wavelength,float speed,float amplitude) {
    vec2 d=normalize(direction);
    float k=6.2831853/wavelength;
    float phase=k*dot(p,d)-clock_seconds*speed;
    return vec3(d.x*k*amplitude*cos(phase),amplitude*sin(phase),d.y*k*amplitude*cos(phase));
}

void vertex() {
    world_surface=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
}

void fragment() {
    vec2 p=world_surface.xz;
    vec2 drift=normalize(flow_direction)*clock_seconds*0.027;
    vec2 warp=vec2(noise(p*.38+clock_seconds*.035),noise(p*.38+vec2(17.3,9.7)-clock_seconds*.024))-.5;
    vec2 uv=p*.21-drift+warp*.11;
    vec3 crust=texture(molten_basalt,uv).rgb;
    if(detail>0) {
        vec3 folds=texture(molten_basalt,uv*1.37+warp*.08+vec2(clock_seconds*.006,-clock_seconds*.009)).rgb;
        crust=mix(crust,folds,.18);
    }
    float heat=smoothstep(.10,.68,crust.r-max(crust.b,crust.g*.25));
    vec3 wave=swell(p,flow_direction,3.8,.23,.035)+swell(p,vec2(-.6,.8),1.3,.41,.012);
    vec2 gradient=wave.xz+vec2(dFdx(heat),dFdy(heat))*.12;
    NORMAL=normalize((VIEW_MATRIX*vec4(normalize(vec3(-gradient.x,1.0,-gradient.y)),0.0)).xyz);
    ALBEDO=mix(crust*.48,vec3(.12,.018,.004),heat*.55);
    ROUGHNESS=mix(.94,.34,heat);
    METALLIC=0.0;
    float pulse=.86+.14*sin(clock_seconds*.7+noise(p*.31)*6.28);
    EMISSION=crust*heat*(2.6+1.3*heat)*pulse;
    // Short expanding incandescent ripples follow each geometric bubble burst.
    if(bubble_phase>=1.0 && bubble_phase<1.65) {
        float age=(bubble_phase-1.0)/.65;
        float radius=bubble_radius*(1.0+age*2.0);
        float ring=1.0-smoothstep(bubble_radius*.06,bubble_radius*.2,abs(length(p-bubble_center)-radius));
        EMISSION+=vec3(3.5,.55,.025)*ring*(1.0-age);
    }
}
