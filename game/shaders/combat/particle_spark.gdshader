shader_type spatial;
render_mode unshaded, cull_back;
uniform vec4 spark_color : source_color = vec4(1.0,0.85,0.02,1.0);
uniform float emission_energy = 6.0;
void fragment() {
    ALBEDO = spark_color.rgb;
    EMISSION = spark_color.rgb*emission_energy;
}
