shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

// Crater lake: analytic swell derivatives, capillary normals, spectral
// absorption, guarded refraction, shoreline wash and refracted caustic cells.
uniform sampler2D scene_depth : hint_depth_texture, filter_nearest, repeat_disable;
uniform sampler2D scene_color : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform vec3 deep_color : source_color = vec3(0.009, 0.055, 0.082);
uniform vec3 shallow_color : source_color = vec3(0.055, 0.28, 0.26);
uniform vec3 foam_color : source_color = vec3(0.75, 0.87, 0.86);
uniform vec3 absorption = vec3(0.34, 0.095, 0.048);
uniform float clock_seconds = 0.0;
uniform float wave_height : hint_range(0.0, 1.0) = 0.18;
uniform float refraction_strength : hint_range(0.0, 0.05) = 0.012;
uniform float foam_width : hint_range(0.1, 3.0) = 0.4;
uniform float caustic_strength : hint_range(0.0, 2.0) = 0.18;
uniform int detail : hint_range(0, 2) = 2;
uniform float lake_radius = 75.0;
varying vec3 world_surface;
varying vec3 swell_gradient;

float hash(vec2 p) {
    vec3 q = fract(vec3(p.xyx) * vec3(0.1031, 0.11369, 0.13787));
    q += dot(q, q.yzx + 19.19);
    return fract((q.x + q.y) * q.z);
}

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f*f*(3.0-2.0*f);
    return mix(mix(hash(i), hash(i+vec2(1.0,0.0)), u.x),
               mix(hash(i+vec2(0.0,1.0)), hash(i+vec2(1.0)), u.x), u.y);
}

float foam_noise(vec2 p) {
    return noise(p)*0.57 + noise(p*2.07+vec2(17.1,8.7))*0.29
         + noise(p*4.31+vec2(2.5,31.3))*0.14;
}

// Y is elevation; X/Z are exact world-space partial derivatives.
vec3 swell(vec2 p, vec2 direction, float wavelength, float speed, float amplitude) {
    vec2 d = normalize(direction);
    float k = 6.2831853/wavelength;
    float phase = k*dot(p,d)-clock_seconds*speed;
    return vec3(d.x*k*amplitude*cos(phase),amplitude*sin(phase),d.y*k*amplitude*cos(phase));
}

vec3 waves(vec2 p) {
    p += vec2(noise(p*0.055),noise(p*0.055+vec2(31.7,8.3)))*3.5;
    vec3 result = swell(p,vec2(0.8,0.6),12.8,1.1,0.56);
    result += swell(p,vec2(-0.32,0.94),7.1,1.53,0.27);
    result += swell(p,vec2(0.91,-0.41),3.3,2.7,0.12);
    result += swell(p,vec2(-0.76,-0.65),1.4,3.8,0.05);
    return result*wave_height;
}

vec3 scene_position(vec2 uv, mat4 inverse_projection, mat4 inverse_view) {
    float depth = texture(scene_depth,uv).r;
    vec3 ndc = vec3(uv*2.0-1.0,depth);
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
    ndc.z = depth*2.0-1.0;
#endif
    vec4 view = inverse_projection*vec4(ndc,1.0);
    view /= view.w;
    return (inverse_view*view).xyz;
}

float cells(vec2 p) {
    vec2 base = floor(p), f = fract(p);
    float first = 8.0, second = 8.0;
    for (int x=-1;x<=1;x++) {
        for (int y=-1;y<=1;y++) {
            vec2 offset = vec2(float(x),float(y));
            vec2 seed = vec2(hash(base+offset), hash(base+offset+31.7));
            vec2 at = offset + 0.5+0.32*sin(seed*6.2831853+clock_seconds*0.35)-f;
            float d = dot(at,at);
            if (d<first) { second=first;first=d; } else { second=min(second,d); }
        }
    }
    return 1.0-smoothstep(0.015,0.13,second-first);
}

void vertex() {
    vec3 world = (MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
    swell_gradient = waves(world.xz);
    swell_gradient *= 1.0-smoothstep(lake_radius-10.0,lake_radius,length(world.xz));
    VERTEX.y += swell_gradient.y;
    world_surface = (MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
}

void fragment() {
    vec2 p = world_surface.xz;
    float distance_to_camera = length(CAMERA_POSITION_WORLD-world_surface);
    float swell_fade = 1.0-smoothstep(150.0,500.0,distance_to_camera);
    vec3 surface_wave = vec3(0.0);
    if (swell_fade>0.001) surface_wave=waves(p);
    float micro_fade = 1.0-smoothstep(45.0,180.0,distance_to_camera);
    vec2 drift = vec2(clock_seconds*0.13,-clock_seconds*0.09);
    vec2 micro = vec2(0.0);
    if (detail>0 && micro_fade>0.001) {
        vec2 uv = p*2.6+drift;
        float n = noise(uv);
        micro = vec2(noise(uv+vec2(0.08,0.0))-n,noise(uv+vec2(0.0,0.08))-n)*1.4;
        micro += vec2(sin(p.x*11.7+p.y*8.1+clock_seconds*3.1),
                      cos(p.y*13.2-p.x*6.2-clock_seconds*2.7))*0.014;
    }
    vec3 normal_world = normalize(vec3(-surface_wave.x*swell_fade-micro.x*micro_fade,1.0,-surface_wave.z*swell_fade-micro.y*micro_fade));
    NORMAL = normalize((VIEW_MATRIX*vec4(normal_world,0.0)).xyz);
    if (!FRONT_FACING) NORMAL = -NORMAL;
    vec3 behind = scene_position(SCREEN_UV,INV_PROJECTION_MATRIX,INV_VIEW_MATRIX);
    float thickness = clamp(world_surface.y-behind.y,0.0,80.0);
    float raw_depth = texture(scene_depth,SCREEN_UV).r;
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
    if (raw_depth>0.99999) thickness=80.0;
#else
    if (raw_depth<0.00001) thickness=80.0;
#endif
    vec2 offset = NORMAL.xy*refraction_strength*min(thickness,3.0)/max(1.0,distance_to_camera*0.035);
    vec2 refracted_uv = clamp(SCREEN_UV+offset,vec2(0.001),vec2(0.999));
    vec3 refracted_point = scene_position(refracted_uv,INV_PROJECTION_MATRIX,INV_VIEW_MATRIX);
    // Reject foreground samples so island silhouettes never smear into water.
    if (refracted_point.y>world_surface.y+0.02) refracted_uv=SCREEN_UV;
    vec3 transmittance = exp(-absorption*thickness);
    vec3 transmission = textureLod(scene_color,refracted_uv,min(distance_to_camera*0.002,1.4)).rgb;
    vec3 water = mix(deep_color,shallow_color,exp(-thickness*0.17));
    float facing = clamp(dot(normalize(VIEW),NORMAL),0.0,1.0);
    float fresnel = 0.0204+0.9796*pow(1.0-facing,5.0);
    float shore = 1.0-smoothstep(0.05,foam_width,thickness);
    float breakup = foam_noise(p*1.35+drift*0.8);
    float wash = sin(thickness*8.0-clock_seconds*2.3+breakup*4.0)*0.5+0.5;
    float contact = shore*smoothstep(0.22,0.72,breakup+wash*0.18);
    float whitecaps = smoothstep(wave_height*0.58,wave_height*0.92,surface_wave.y)*smoothstep(0.67,0.88,breakup)*0.28*swell_fade;
    float foam = clamp(contact+whitecaps,0.0,1.0);
    vec3 caustics = vec3(0.0);
    if (detail>1 && thickness<12.0) {
        float ca = cells(behind.xz*0.7+drift*0.5);
        ca *= cells(behind.xz*0.77-drift*0.4+3.8);
        caustics = vec3(0.38,0.78,0.63)*ca*caustic_strength*exp(-thickness*0.24)*(1.0-shore);
    }
    // Reflection lighting is supplied by the environment through dielectric
    // specular; transmission is emissive to avoid lighting it a second time.
    ALBEDO = mix(water,foam_color,foam);
    EMISSION = (transmission*transmittance*(1.0-fresnel)+caustics)*(1.0-foam)*0.62;
    ROUGHNESS = mix(0.12+micro_fade*0.035,0.82,foam);
    SPECULAR = 0.255;
    METALLIC = 0.0;
    ALPHA = 1.0;
}
