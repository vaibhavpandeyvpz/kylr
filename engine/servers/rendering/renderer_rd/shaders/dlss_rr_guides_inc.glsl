#ifndef DLSS_RR_GUIDES_INC
#define DLSS_RR_GUIDES_INC

// Same environment-BRDF guide approximation as raytracing/brdf_inc.glsl.
// Matrix coefficients are row-initialized, then transposed for GLSL.
vec3 dlss_rr_guide_env_brdf(vec3 specular_color, float roughness, float ndotv) {
	float alpha = roughness * roughness;
	float nv = abs(ndotv);
	vec4 x = vec4(1.0, nv, nv * nv, nv * nv * nv);
	vec4 y = vec4(1.0, alpha, alpha * alpha, alpha * alpha * alpha);
	mat2 m1 = transpose(mat2(0.99044, -1.28514, 1.29678, -0.755907));
	mat3 m2 = transpose(mat3(1.0, 2.92338, 59.4188, 20.3225, -27.0302, 222.592, 121.563, 626.13, 316.627));
	mat2 m3 = transpose(mat2(0.0365463, 3.32707, 9.0632, -9.04756));
	mat3 m4 = transpose(mat3(1.0, 3.59685, -1.36772, 9.04401, -16.3174, 9.22949, 5.56589, 19.7886, -20.2123));
	float bias = dot(m1 * x.xy, y.xy) / max(dot(m2 * x.xyw, y.xyw), 1e-6);
	float scale = dot(m3 * x.xy, y.xy) / max(dot(m4 * x.xzw, y.xyw), 1e-6);
	bias *= clamp(specular_color.g * 50.0, 0.0, 1.0);
	return specular_color * max(scale, 0.0) + max(bias, 0.0);
}
#endif
