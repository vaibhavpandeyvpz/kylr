shader_type spatial;
render_mode cull_back, depth_draw_opaque;

uniform vec4 bubble_albedo : source_color;
uniform vec4 bubble_emission : source_color;
uniform float bubble_energy = 2.5;
uniform float bubble_roughness = 0.38;
uniform float clock_seconds = 0.0;

void vertex() {
    float age = (clock_seconds - INSTANCE_CUSTOM.x) / INSTANCE_CUSTOM.y;
    if (INSTANCE_CUSTOM.w < 0.5) {
        float grow = smoothstep(0.0, 0.65, age) * (1.0 - smoothstep(0.72, 0.86, age));
        if (age < 0.0 || age > 0.86) grow = 0.0;
        VERTEX *= grow;
        VERTEX.y = VERTEX.y * 0.75 - (1.0 - grow) * 1.2;
    } else {
        float pop = (age - 0.72) / 0.48;
        if (pop <= 0.0 || pop >= 1.0) {
            VERTEX = vec3(0.0, -2.0, 0.0);
        } else {
            float angle = INSTANCE_CUSTOM.z + INSTANCE_CUSTOM.w * 2.0943951;
            VERTEX *= 0.12 * (1.0 - pop);
            VERTEX += vec3(cos(angle)*pop*0.6, 2.0*pop*(1.0-pop), sin(angle)*pop*0.6);
        }
    }
}

void fragment() {
    ALBEDO = bubble_albedo.rgb;
    EMISSION = bubble_emission.rgb * bubble_energy;
    ROUGHNESS = bubble_roughness;
}
