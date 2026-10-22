// Compact fuel-rich contact: prolonged flame, sparse cooling soot.
shader_type spatial;
render_mode unshaded, blend_mix, cull_front, depth_draw_never, depth_test_disabled;
uniform sampler2D turbulence : filter_linear_mipmap, repeat_enable;
uniform sampler3D density_volume : filter_linear, repeat_enable;
uniform sampler2D albedo_height : filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_roughness : filter_linear_mipmap, repeat_enable;
uniform sampler2D scene_depth : hint_depth_texture, filter_nearest, repeat_disable;
uniform int layer = 0; // burning gas, cooling soot, ignition core, neutral dust
uniform float phase = 0.0;
uniform int march_steps : hint_range(8,32) = 24;
uniform float emission = 2.6;
uniform float effect_emission = 1.0;
uniform float effect_opacity = 1.0;
uniform vec3 impact_origin;
instance uniform float progress = 0.0;
varying vec3 cloud_surface;
varying vec3 camera_local;
varying vec3 light_local;
float noise3(vec3 p) {
    return texture(density_volume,p*0.7).r;
}
void vertex() {
    cloud_surface = VERTEX;
    camera_local = (inverse(MODEL_MATRIX)*INV_VIEW_MATRIX[3]).xyz;
    light_local = normalize((inverse(MODEL_MATRIX)*vec4(-0.3,0.8,0.4,0.0)).xyz);
}
void fragment() {
    vec3 direction = normalize(cloud_surface-camera_local);
    float along = dot(camera_local,direction);
    float discriminant = along*along-dot(camera_local,camera_local)+0.48*0.48;
    if (discriminant<=0.0) discard;
    float root = sqrt(discriminant);
    float begin = max(-along-root,0.0);
    float end = -along+root;
    // Clip against opaque world depth instead of the far proxy face.
    // The same ray interval works when the camera is inside the cloud.
    float depth = texture(scene_depth,SCREEN_UV).r;
    if (depth>0.000001) {
        vec4 view_point = INV_PROJECTION_MATRIX*vec4(SCREEN_UV*2.0-1.0,depth,1.0);
        view_point /= view_point.w;
        vec3 obstacle = (inverse(MODEL_MATRIX)*INV_VIEW_MATRIX*view_point).xyz;
        end = min(end,dot(obstacle-camera_local,direction));
    }
    if (end<=begin) discard;
    float step_size = (end-begin)/float(march_steps);
    float angle = progress*2.6+phase;
    mat2 turn = mat2(vec2(cos(angle),sin(angle)),vec2(-sin(angle),cos(angle)));
    float birth = smoothstep(0.0,0.025,progress);
    float tail = 1.0-smoothstep(layer==3 ? 0.38 : 0.62,1.0,progress);
    float cooling = smoothstep(0.4,1.0,progress)*0.65;
    vec3 color_sum = vec3(0.0);
    vec3 fire_sum = vec3(0.0);
    float alpha = 0.0;
    // Decorrelate the ray samples so a rotating cloud cannot reveal stacked
    // integration slices. Stable screen-space jitter distributes integration samples.
    float jitter = 0.4+fract(sin(dot(FRAGCOORD.xy,vec2(12.9898,78.233)))*43758.5453)*0.2;
    for (int i=0;i<32;i++) {
        if (i>=march_steps || alpha>0.985) break;
        vec3 position = camera_local+direction*(begin+(float(i)+jitter)*step_size);
        vec3 p = position*1.3;
        p.xz = turn*p.xz;
        p += vec3(phase,-progress*2.5,phase*0.61);
        p += (texture(turbulence,p.yz*.27).rgb-0.5)*0.18;
        float coarse = noise3(p);
        float fine = noise3(p*2.57+vec3(1.7,5.3,2.1));
        vec2 material_uv = vec2(atan(position.z,position.x)/TAU+phase,(position.y+0.4)*1.4-progress*1.8);
        vec4 material_color = textureLod(albedo_height,material_uv,1.0);
        float relief_height = material_color.a;
        float turbulence_density = coarse*0.3+fine*0.2+relief_height*0.5;
        float radius = 0.35+(coarse-0.4)*0.25+(fine-0.5)*0.06;
        float shell = 1.0-smoothstep(radius-(layer==3 ? 0.065 : 0.035),radius,length(position));
        float flame_height = clamp((position.y+0.36)/0.78,0.0,1.0);
        float flame_radial = 0.0;
        if (layer==0) {
            vec2 curl = vec2(sin(flame_height*6.0-progress*8.0+phase),cos(flame_height*5.0-progress*6.0+phase))*flame_height*0.085;
            float taper = (0.23*pow(1.0-flame_height,0.8)+0.012)*(0.75+coarse*0.5);
            taper *= 1.0-smoothstep(0.55,1.0,progress)*0.6;
            flame_radial = length(position.xz-curl)/max(taper,0.001);
            shell = (1.0-smoothstep(0.55,1.0,flame_radial))*smoothstep(-0.4,-0.3,position.y);
            shell *= 1.0-smoothstep(0.27+fine*0.12,0.42,position.y);
        }
        float density = shell*smoothstep(mix(0.20,0.43,progress),mix(0.56,0.7,progress),turbulence_density);
        density *= mix(1.0,0.5+relief_height*1.4,smoothstep(0.65,1.0,length(position)/radius));
        if (layer==0 || layer==4) density *= mix(0.15,0.95,smoothstep(0.08,0.55,relief_height));
        if (layer==4) density *= 0.06;
        float heat = clamp(turbulence_density*1.8+0.05-progress*0.6-flame_height*0.26-flame_radial*0.18,0.0,1.0);
        vec3 fire = mix(vec3(0.75,0.045,0.003),vec3(1.0,0.31,0.015),smoothstep(0.15,0.65,heat));
        fire = mix(fire,vec3(1.0,0.67,0.12),smoothstep(0.88,1.0,heat)*0.5);
        if (layer==0 || layer==4) fire = mix(fire,material_color.rgb,0.35);
        vec4 relief = textureLod(normal_roughness,material_uv,1.0);
        vec3 gradient = vec3(noise3(p+vec3(0.025,0.0,0.0)),
            noise3(p+vec3(0.0,0.025,0.0)),noise3(p+vec3(0.0,0.0,0.025)))-vec3(coarse);
        vec3 relief_normal = normalize(-gradient*18.0+normalize(position+vec3(0.001))*0.25+(relief.xyz*2.0-1.0)*0.06);
        float diffuse = max(dot(relief_normal,light_local),0.0);
        float light = (0.22+diffuse*0.78)*exp(-density*0.3);
        vec3 soot = material_color.rgb*light;
        soot += vec3(0.035)*pow(diffuse,mix(16.0,2.0,relief.a))*(1.0-relief.a);
        vec3 color;
        vec3 glow;
        if (layer==1 || layer==3) {
            density *= layer==1 ? smoothstep(0.12,0.45,progress)*0.2 : 0.85;
            float pockets = layer==1 ? smoothstep(0.57,0.72,turbulence_density)*(1.0-smoothstep(0.06,0.3,progress)) : 0.0;
            color = mix(soot,fire,pockets*0.45);
            glow = fire*pockets*0.5;
            if (layer==3) {
                color = mix(vec3(0.12,0.13,0.14),vec3(0.25,0.26,0.27),diffuse);
                vec3 world_position = (MODEL_MATRIX*vec4(position,1.0)).xyz;
                float ignition = (1.0-smoothstep(0.02,0.34,length(world_position-impact_origin)))
                    *(1.0-smoothstep(0.025,0.12,progress));
                color = mix(color,vec3(0.8,0.3,0.035),ignition);
                glow = vec3(1.0,0.5,0.09)*ignition;
            }
        } else if (layer==2) {
            density *= 1.0-smoothstep(0.025,0.13,progress);
            color = vec3(1.0,0.67,0.16);
            glow = vec3(1.0,0.8,0.38);
        } else {
            float burning = smoothstep(0.05,0.35,heat)*(1.0-cooling);
            color = mix(soot,fire,burning);
            glow = fire*burning*heat;
        }
        float opacity = (1.0-exp(-density*step_size*(layer==0 ? 12.0 : 18.0)))*birth*tail*effect_opacity;
        float weight = (1.0-alpha)*opacity;
        color_sum += color*weight;
        fire_sum += glow*weight;
        alpha += weight;
    }
    if (alpha<0.005) discard;
    ALBEDO = color_sum/max(alpha,0.001);
    EMISSION = fire_sum/max(alpha,0.001)*emission*effect_emission*0.32;
    ALPHA = alpha;
}
