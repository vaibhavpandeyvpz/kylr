// Light sampling and Next Event Estimation (NEE) for raytracing.
// Requires: raytracing_inc.glsl, brdf_inc.glsl, tlas at binding 1, payload at location 0.
// Note: ray_query_alpha_test() still requires GL_EXT_ray_query (used by DLSS-RR path or when USE_RAY_QUERY_SHADOWS is defined).

// ============================================================================
// Light Types and Constants
// ============================================================================

#define RT_LIGHT_TYPE_OMNI 0 // Point light with radius (soft shadows)
#define RT_LIGHT_TYPE_DIRECTIONAL 1 // Sun/moon with angular size
#define RT_LIGHT_TYPE_AREA 2 // One-sided rectangular emitter
#define RT_LIGHT_TYPE_SPOT 3 // Spot light with cone falloff

// Reservoir sampling batch size for stochastic light selection.
#ifndef RT_LIGHT_RESERVOIR_SIZE
#define RT_LIGHT_RESERVOIR_SIZE 16
#endif

#if defined(DLSS_RR_ENABLED)
#define RT_IMPORTANCE_LIGHT_SAMPLING
#endif

// ============================================================================
// Light Data (matches C++ RT_LightData, 112 bytes, std430)
// ============================================================================

struct RTLightData {
	vec3 position; // World pos (omni/spot) or direction (directional).
	uint type; // RT_LIGHT_TYPE_*.
	vec3 emission; // HDR emission color (color * energy).
	float radius; // Light size (omni/spot) or angular radius (directional).
	float attenuation; // Attenuation exponent (2=inverse-square, 1=linear).
	float inv_max_range; // 1/range (-1 = infinite).
	float max_range_squared; // range^2 (0 = infinite).
	float specular_amount; // Godot specular multiplier [0..1].
	float indirect_energy; // Godot indirect energy multiplier.
	float inv_spot_attenuation; // Spot cone softness.
	float cos_spot_angle; // Cosine of spot cone half-angle.
	uint shadow_enabled; // Light3D shadow control, independent of raster maps.
	vec3 spot_direction; // Spot direction (normalized, world space).
	float proposal_pdf;
	vec3 area_u;
	float alias_probability;
	vec3 area_v;
	uint alias_index;
};

// Light buffer SSBO (binding provided by the including shader via RT_LIGHT_BUFFER_BINDING).
#ifndef RT_LIGHT_BUFFER_BINDING
#define RT_LIGHT_BUFFER_BINDING 13
#endif

layout(set = 0, binding = RT_LIGHT_BUFFER_BINDING, std430) readonly buffer LightBuffer {
	RTLightData rt_lights[];
};

// ============================================================================
// Unified Cone Sampling (for sphere, directional, spot lights)
// ============================================================================

struct LightSample {
	vec3 cone_axis; // Direction to sample around (normalized).
	float cos_theta_max; // Cone half-angle cosine (1.0 = point, 0.0 = hemisphere).
	vec3 emission; // Light radiance.
	float distance_sq; // Squared distance to light (0 = directional).
	float max_distance; // Max shadow ray distance.
};

// Build orthonormal basis from a single direction.
void lights_build_basis(vec3 dir, out vec3 tangent, out vec3 bitangent) {
	vec3 up = abs(dir.z) < 0.999 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
	tangent = normalize(cross(up, dir));
	bitangent = cross(dir, tangent);
}

// Transform local direction to world space around axis.
vec3 lights_local_to_world(vec3 local_dir, vec3 axis) {
	vec3 tangent, bitangent;
	lights_build_basis(axis, tangent, bitangent);
	return local_dir.x * tangent + local_dir.y * bitangent + local_dir.z * axis;
}

// Prepare unified cone sample from any light type.
LightSample lights_prepare_sample(vec3 hit_pos, RTLightData light) {
	LightSample s;

	vec3 to_light = light.position - hit_pos;
	float dist_sq = dot(to_light, to_light);
	float inv_dist = inversesqrt(dist_sq + 1e-10);
	float dist = dist_sq * inv_dist;

	float is_directional = (light.type == RT_LIGHT_TYPE_DIRECTIONAL) ? 1.0 : 0.0;

	// Cone axis.
	vec3 sphere_axis = to_light * inv_dist;
	vec3 dir_axis = -normalize(light.position);
	s.cone_axis = mix(sphere_axis, dir_axis, is_directional);

	// Distance (0 for directional = no falloff).
	s.distance_sq = mix(dist_sq, 0.0, is_directional);

	// Cone angle from subtended solid angle.
	float sin_theta_sphere = clamp(light.radius * inv_dist, 0.0, 1.0);
	float cos_theta_sphere = sqrt(max(0.0, 1.0 - sin_theta_sphere * sin_theta_sphere));
	float cos_theta_dir = cos(light.radius);
	s.cos_theta_max = mix(cos_theta_sphere, cos_theta_dir, is_directional);
	s.cos_theta_max = min(s.cos_theta_max, 0.999999);

	s.emission = light.emission;

	// Max shadow ray distance.
	float sphere_max = dist + light.radius;
	float dir_max = 10000.0;
	s.max_distance = mix(sphere_max, dir_max, is_directional);

	return s;
}

// Sample a direction within the light's cone.
vec3 lights_sample_cone(LightSample ls, vec2 u, out float pdf) {
	float cos_theta = 1.0 - u.x * (1.0 - ls.cos_theta_max);
	float sin_theta = sqrt(max(0.0, 1.0 - cos_theta * cos_theta));
	float phi = 2.0 * PI * u.y;

	vec3 local_dir = vec3(sin_theta * cos(phi), sin_theta * sin(phi), cos_theta);
	vec3 L = lights_local_to_world(local_dir, ls.cone_axis);

	float solid_angle = 2.0 * PI * (1.0 - ls.cos_theta_max);
	pdf = 1.0 / max(solid_angle, 1e-10);

	return L;
}

// ============================================================================
// Attenuation
// ============================================================================

// Godot-style windowed distance attenuation.
// window = (1 - (d/range)^4)^2, combined with pow(d, -decay).
float lights_get_attenuation(LightSample ls, float inv_max_range, float decay) {
	if (ls.distance_sq <= 0.0) {
		return 1.0; // Directional: no distance attenuation.
	}

	float distance = sqrt(ls.distance_sq);
	float atten = min(pow(max(distance, 0.0001), -decay), 1.0);

	// Windowed falloff if range is finite (inv_max_range >= 0).
	if (inv_max_range >= 0.0) {
		float nd = distance * inv_max_range;
		nd *= nd;
		nd *= nd; // nd^4
		nd = max(1.0 - nd, 0.0);
		nd *= nd; // nd^2 window
		return atten * nd;
	}

	return atten;
}

// Per-light specular multiplier.
float lights_get_specular_multiplier(float specular_amount, float roughness) {
	if (specular_amount >= 0.0) {
		return specular_amount;
	} else {
		float r3 = roughness * roughness * roughness;
		return mix(0.0, r3, -specular_amount);
	}
}

// ============================================================================
// Inline Alpha Test (shared by all ray query proceed loops)
// ============================================================================

/// Inline alpha test for ray query candidates. Returns true if the hit is opaque (alpha >= 0.5).
/// Mirrors the any-hit shader logic for use with inline ray queries.
bool ray_query_alpha_test(uint geometry_idx, uint primitive_id, vec2 candidate_bary) {
	vec3 bary = vec3(1.0 - candidate_bary.x - candidate_bary.y, candidate_bary.x, candidate_bary.y);

	GeometryData geom = geometries[geometry_idx];
	uint i0, i1, i2;
	get_triangle_indices_ex(geom, primitive_id, i0, i1, i2);
	vec2 uv = fetch_uv(geom, i0, i1, i2, bary);

	MaterialData mat = materials[geometry_idx];
	uv = uv * mat.uv1_scale + mat.uv1_offset;
	float alpha = texture(sampler2D(bindless_textures[nonuniformEXT(mat.albedo_texture_idx)], SAMPLER_LINEAR_WITH_MIPMAPS_REPEAT), uv).a;
	alpha *= mat.albedo_color.a;

	return alpha >= 0.5;
}

// ============================================================================
// Shadow Ray (traceRayEXT pipeline)
// ============================================================================

/// Returns true if light is visible.
/// Uses SkipClosestHitShader so only any_hit (alpha test) and miss are invoked.
/// TerminateOnFirstHit causes early exit on first confirmed opaque hit.
bool lights_trace_shadow_ray_pipeline(vec3 origin, vec3 direction, float max_dist, inout uint rng_state) {
#if defined(USE_SER)
	hitObjectEXT hitObject;
	hitObjectTraceRayEXT(hitObject, tlas,
			gl_RayFlagsTerminateOnFirstHitEXT | gl_RayFlagsSkipClosestHitShaderEXT,
			0xFF, 0, 0, 0,
			origin, 0.001, direction, max_dist - 0.001, 0);

	return !(hitObjectIsHitEXT(hitObject));
#else
	/// The miss shader writes radiance = vec3(1.0) for shadow rays (visible).
	/// If an opaque hit occurs, miss is never called and radiance stays vec3(0.0).
	// Save full payload, set up shadow ray, then restore after trace.
	PathPayload saved_payload = payload;

	PathState shadow_ps;
	shadow_ps.radiance = vec3(0.0);
	shadow_ps.throughput = vec3(0.0);
	shadow_ps.packed_bounces_flags = set_shadow_ray(0u);
	shadow_ps.rng_state = 0u;
	shadow_ps.hit_t = 0.0;
	shadow_ps.offset_normal = vec3(0.0, 0.0, 1.0);
	shadow_ps.next_ray_dir = vec3(0.0, 0.0, 1.0);
	path_pack(payload, shadow_ps);

	traceRayEXT(tlas,
			gl_RayFlagsTerminateOnFirstHitEXT | gl_RayFlagsSkipClosestHitShaderEXT,
			0xFF, 0, 0, 0,
			origin, 0.001, direction, max_dist - 0.001, 0);

	// Unpack to check visibility (miss shader packs radiance = 1.0).
	shadow_ps = path_unpack(payload);
	bool visible = shadow_ps.radiance.x > 0.5;

	payload = saved_payload;

	return visible;
#endif
}

bool lights_trace_shadow_ray(vec3 origin, vec3 direction, float max_dist, inout uint rng_state) {
#ifdef USE_RAY_QUERY_SHADOWS
	rayQueryEXT shadow_rq;
	rayQueryInitializeEXT(shadow_rq, tlas,
			gl_RayFlagsTerminateOnFirstHitEXT,
			0xFF, origin, 0.001, direction, max_dist - 0.001);
	while (rayQueryProceedEXT(shadow_rq)) {
		// Opaque geometry is committed by traversal. Any reported candidate
		// needs the actual material shader (or procedural intersection shader).
		// Restart through the full pipeline instead of approximating its alpha.
		rayQueryTerminateEXT(shadow_rq);
		return lights_trace_shadow_ray_pipeline(origin, direction, max_dist, rng_state);
	}
	return rayQueryGetIntersectionTypeEXT(shadow_rq, true) == gl_RayQueryCommittedIntersectionNoneEXT;
#else
	return lights_trace_shadow_ray_pipeline(origin, direction, max_dist, rng_state);
#endif
}

// ============================================================================
// Next Event Estimation (NEE) - Direct Light Sampling
// ============================================================================

#ifdef RT_IMPORTANCE_LIGHT_SAMPLING
// Conservative world-space cell masks. Header words and ascending mask bits
// match RenderRaytracing::update_light_grid. Disabled indices use the full set.
layout(set = 0, binding = 47, std430) readonly buffer LightGridBuffer {
	uint rt_light_grid[];
};

uvec2 lights_cell_mask(vec3 hit_pos) {
	vec3 origin = uintBitsToFloat(uvec3(rt_light_grid[0], rt_light_grid[1], rt_light_grid[2]));
	float inverse_width = uintBitsToFloat(rt_light_grid[3]);
	uvec3 dimensions = uvec3(rt_light_grid[4], rt_light_grid[5], rt_light_grid[6]);
	vec3 cell = floor((hit_pos - origin) * inverse_width);
	if (!all(greaterThanEqual(cell, vec3(0.0))) || !all(lessThan(cell, vec3(dimensions)))) {
		return uvec2(rt_light_grid[8], rt_light_grid[9]);
	}
	uvec3 index = uvec3(cell);
	uint offset = 12u + 2u * (index.x + dimensions.x * (index.y + dimensions.y * index.z));
	return uvec2(rt_light_grid[offset], rt_light_grid[offset + 1u]);
}

// Positive, inexpensive target for initial reservoir resampling. Visibility is
// evaluated only for the selected light. Keep nonzero support at grazing angles
// because finite emitters can illuminate a surface even when their center cannot.
float lights_resampling_target(RTLightData light, vec3 hit_pos, vec3 N, vec3 V, MaterialProperties material, bool indirect) {
	bool positional = light.type != RT_LIGHT_TYPE_DIRECTIONAL;
	// Reject zero-support candidates before constructing their cone or BRDF.
	// These checks consume no random numbers and retain the original support.
	if (positional && light.max_range_squared > 0.0) {
		vec3 to_light = light.position - hit_pos;
		if (dot(to_light, to_light) > light.max_range_squared) {
			return 0.0;
		}
	}
	LightSample sample_info = lights_prepare_sample(hit_pos, light);
	float area_length = 0.0;
	float emitter_cosine = 0.0;
	if (light.type == RT_LIGHT_TYPE_AREA) {
		vec3 normal_area = cross(light.area_u, light.area_v);
		area_length = length(normal_area);
		if (area_length <= 1e-8) {
			return 0.0;
		}
		emitter_cosine = dot(sample_info.cone_axis, normal_area / area_length);
		if (emitter_cosine <= 0.0) {
			return 0.0;
		}
	}
	vec3 emission = max(light.emission, vec3(0.0));
	float emitter_radius = light.type == RT_LIGHT_TYPE_AREA ? max(length(light.area_u), length(light.area_v)) : light.radius;
	float angular_radius = positional ? emitter_radius * inversesqrt(max(sample_info.distance_sq, 1e-8)) : sin(light.radius);
	// Widen only the proposal lobe to cover a finite emitter. The evaluated
	// BRDF and radiance remain unchanged; this target controls selection only.
	MaterialProperties proposal_material = material;
	proposal_material.roughness = max(material.roughness, sqrt(clamp(angular_radius, 0.0, 1.0)));
	vec3 proposal_diffuse, proposal_specular;
	evalCombinedBRDFSeparate(N, sample_info.cone_axis, V, proposal_material, proposal_diffuse, proposal_specular);
	float specular_multiplier = lights_get_specular_multiplier(light.specular_amount, proposal_material.roughness);
	float target = dot((proposal_diffuse + proposal_specular * specular_multiplier) * emission, vec3(0.2126, 0.7152, 0.0722));
	// Retain support when an emitter's center is below the geometric horizon.
	target = max(target, dot(emission, vec3(0.2126, 0.7152, 0.0722)) * 0.001);
	if (positional) {
		target *= lights_get_attenuation(sample_info, light.inv_max_range, light.attenuation);
	}
	if (light.type == RT_LIGHT_TYPE_AREA) {
		target *= 4.0 * area_length * emitter_cosine;
	}
	return target * (indirect ? light.indirect_energy : 1.0);
}
#endif

// Evaluate direct lighting using NEE with stochastic light selection.
// Uses mini-batch reservoir sampling for importance-weighted light selection.
vec3 lights_evaluate_direct_lighting(
		vec3 hit_pos,
		vec3 N,
		vec3 V,
		MaterialProperties material,
		inout uint rng_state,
		bool is_indirect_bounce,
		uint light_count) {
	vec3 diffuse_contribution = vec3(0.0);
	vec3 specular_contribution = vec3(0.0);
	if (light_count == 0u) {
		return vec3(0.0);
	}

	// Temporal denoisers receive one noisy sample per pixel. Evaluate each light's proposal
	// so a bright nearby emitter cannot be absent from a candidate subset.
	// Visibility is still traced only for the selected light.
#ifdef RT_IMPORTANCE_LIGHT_SAMPLING
	bool use_proposals = (RT_FLAGS & RT_FLAG_LIGHT_PROPOSALS) != 0u && rt_lights[0].proposal_pdf > 0.0;
	bool use_light_grid = !use_proposals && rt_light_grid[10] != 0u;
	uvec2 candidates = use_light_grid ? lights_cell_mask(hit_pos) : uvec2(0u);
	uint k = use_proposals ? min(16u, light_count) : (use_light_grid ? uint(bitCount(candidates.x) + bitCount(candidates.y)) : light_count);
#else
	uint k = uint(min(RT_LIGHT_RESERVOIR_SIZE, int(light_count)));
#endif
	uint valid_found = 0u;
	uint selected_idx = 0u;
#ifdef RT_IMPORTANCE_LIGHT_SAMPLING
	float weight_sum = 0.0;
	float selected_weight = 0.0;
#endif

	for (uint i = 0u; i < k; i++) {
#ifdef RT_IMPORTANCE_LIGHT_SAMPLING
		uint idx = i;
		if (use_proposals) {
			uint column = min(uint(rand(rng_state) * float(light_count)), light_count - 1u);
			idx = rand(rng_state) < rt_lights[column].alias_probability ? column : rt_lights[column].alias_index;
		} else if (use_light_grid) {
			if (candidates.x != 0u) {
				idx = uint(findLSB(candidates.x));
				candidates.x &= candidates.x - 1u;
			} else {
				idx = 32u + uint(findLSB(candidates.y));
				candidates.y &= candidates.y - 1u;
			}
		}
#else
		uint idx = min(uint(rand(rng_state) * float(light_count)), light_count - 1u);
#endif
		RTLightData test_light = rt_lights[idx];

#ifdef RT_IMPORTANCE_LIGHT_SAMPLING
		float target = lights_resampling_target(test_light, hit_pos, N, V, material, is_indirect_bounce);
		float weight = use_proposals ? target / test_light.proposal_pdf : target;
		weight_sum += weight;
		if (weight > 0.0 && rand(rng_state) * weight_sum < weight) {
			selected_idx = idx;
			selected_weight = target;
		}
#else
		// Range check for positional lights.
		bool is_positional = (test_light.type == RT_LIGHT_TYPE_OMNI || test_light.type == RT_LIGHT_TYPE_SPOT || test_light.type == RT_LIGHT_TYPE_AREA);
		bool is_valid = !is_positional;
		if (!is_valid) {
			vec3 to_l = test_light.position - hit_pos;
			float d2 = dot(to_l, to_l);
			is_valid = (test_light.max_range_squared == 0.0 || d2 <= test_light.max_range_squared);
		}

		if (is_valid) {
			valid_found++;
			if (rand(rng_state) < 1.0 / float(valid_found)) {
				selected_idx = idx;
			}
		}
#endif
	}

#ifdef RT_IMPORTANCE_LIGHT_SAMPLING
	if (weight_sum <= 0.0 || selected_weight <= 0.0) {
		return vec3(0.0);
	}
	// For independent proposals: W = sum(target / source_pdf) / (M * selected_target).
	// Enumeration (including conservative zero-support rejection) uses target/sum.
	// Neither path reuses reservoirs across pixels or frames.
	float light_select_pdf = use_proposals ? float(k) * selected_weight / weight_sum : float(light_count) * selected_weight / (float(light_count) * weight_sum);
#else
	if (valid_found == 0u) {
		return vec3(0.0);
	}

	// Estimate valid count from sample ratio, PDF = 1/validCount.
	float valid_count_estimate = float(light_count) * (float(valid_found) / float(k));
	float light_select_pdf = 1.0 / max(valid_count_estimate, 1.0);
#endif

	RTLightData light = rt_lights[selected_idx];
	vec2 u = rand2(rng_state);

	if (light.type == RT_LIGHT_TYPE_AREA) {
		vec3 area_normal = cross(light.area_u, light.area_v);
		float surface_area = 4.0 * length(area_normal);
		if (surface_area <= 1e-8) {
			return vec3(0.0);
		}
		vec3 sampled_position = light.position + (2.0 * u.x - 1.0) * light.area_u + (2.0 * u.y - 1.0) * light.area_v;
		vec3 to_light = sampled_position - hit_pos;
		float distance_sq = dot(to_light, to_light);
		if (distance_sq <= 1e-8 || (light.max_range_squared > 0.0 && distance_sq > light.max_range_squared)) {
			return vec3(0.0);
		}
		float distance = sqrt(distance_sq);
		vec3 L = to_light / distance;
		// Local -Z is the emitting side. cross(U,V) points towards local +Z.
		float emitter_cosine = max(dot(L, normalize(area_normal)), 0.0);
		if (dot(N, L) <= 0.0 || emitter_cosine <= 0.0 || (light.shadow_enabled != 0u && !lights_trace_shadow_ray(hit_pos, L, max(distance - 0.001, 0.0), rng_state))) {
			return vec3(0.0);
		}
		vec3 brdf_diffuse, brdf_specular;
		evalCombinedBRDFSeparate(N, L, V, material, brdf_diffuse, brdf_specular);
		LightSample sample_attenuation;
		sample_attenuation.distance_sq = distance_sq;
		float attenuation = lights_get_attenuation(sample_attenuation, light.inv_max_range, light.attenuation);
		float indirect = is_indirect_bounce ? light.indirect_energy : 1.0;
		vec3 weight = light.emission * (surface_area * emitter_cosine * attenuation * indirect / max(light_select_pdf, 1e-10));
		float specular_multiplier = lights_get_specular_multiplier(light.specular_amount, material.roughness);
		diffuse_contribution = brdf_diffuse * weight;
		specular_contribution = brdf_specular * specular_multiplier * weight;
		return diffuse_contribution + specular_contribution;
	}

	// === POSITIONAL LIGHT PATH (omni + spot) ===
	if (light.type == RT_LIGHT_TYPE_OMNI || light.type == RT_LIGHT_TYPE_SPOT) {
		vec3 to_light = light.position - hit_pos;
		float dist_sq = dot(to_light, to_light);

		// Early out: outside max range.
		if (light.max_range_squared != 0.0 && dist_sq > light.max_range_squared) {
			return vec3(0.0);
		}

		float dist = sqrt(dist_sq);
		vec3 L;
		float shadow_dist;

		if (light.radius <= 0.01) {
			// True point light: exact direction.
			L = to_light / max(dist, 0.0001);
			shadow_dist = dist;
		} else {
			// Sphere light: cone sampling for soft shadows.
			LightSample ls = lights_prepare_sample(hit_pos, light);
			float light_pdf;
			L = lights_sample_cone(ls, u, light_pdf);
			float t_center = dot(to_light, L);
			vec3 perp = to_light - t_center * L;
			float perp_sq = dot(perp, perp);
			float dt = sqrt(max(0.0, light.radius * light.radius - perp_sq));
			shadow_dist = max(0.0, t_center - dt);
		}

		// The BRDF is zero below the shading-normal hemisphere, just as in the
		// directional-light path. Reject these samples before shadow traversal;
		// this preserves light selection and the sampled area-light direction.
		if (dot(N, L) <= 0.0) {
			return vec3(0.0);
		}

		// Spot cone early-out.
		float spot_atten = 1.0;
		if (light.type == RT_LIGHT_TYPE_SPOT) {
			float scos = dot(-L, light.spot_direction);
			if (scos <= light.cos_spot_angle) {
				return vec3(0.0);
			}
			float spot_rim = max(1e-4, (1.0 - scos) / (1.0 - light.cos_spot_angle));
			spot_atten = 1.0 - pow(spot_rim, light.inv_spot_attenuation);
		}

		if (light.shadow_enabled != 0u && !lights_trace_shadow_ray(hit_pos, L, shadow_dist, rng_state)) {
			return vec3(0.0);
		}

		// Evaluate BRDF (diffuse + specular separately for specular_amount control).
		vec3 brdf_diffuse, brdf_specular;
		evalCombinedBRDFSeparate(N, L, V, material, brdf_diffuse, brdf_specular);

		// Distance attenuation.
		LightSample ls_atten;
		ls_atten.distance_sq = dist_sq;
		float atten = lights_get_attenuation(ls_atten, light.inv_max_range, light.attenuation) * spot_atten;

		float spec_mul = lights_get_specular_multiplier(light.specular_amount, material.roughness);
		vec3 brdf_value = brdf_diffuse + brdf_specular * spec_mul;

		float indirect_mul = is_indirect_bounce ? light.indirect_energy : 1.0;

		// NdotL is already included in brdf_value (evalLambertian/evalMicrofacet bake it in).
		vec3 contribution = brdf_value * light.emission * atten * indirect_mul;
		diffuse_contribution = brdf_diffuse * light.emission * atten * indirect_mul / max(light_select_pdf, 1e-10);
		specular_contribution = brdf_specular * spec_mul * light.emission * atten * indirect_mul / max(light_select_pdf, 1e-10);
		return contribution / max(light_select_pdf, 1e-10);
	}
	// === CONE LIGHT PATH (directional) ===
	else {
		LightSample ls = lights_prepare_sample(hit_pos, light);
		float light_pdf;
		vec3 L = lights_sample_cone(ls, u, light_pdf);

		float NdotL = dot(N, L);
		if (NdotL <= 0.0) {
			return vec3(0.0);
		}

		if (light.shadow_enabled != 0u && !lights_trace_shadow_ray(hit_pos, L, ls.max_distance, rng_state)) {
			return vec3(0.0);
		}

		vec3 brdf_diffuse, brdf_specular;
		evalCombinedBRDFSeparate(N, L, V, material, brdf_diffuse, brdf_specular);

		float spec_mul = lights_get_specular_multiplier(light.specular_amount, material.roughness);
		vec3 brdf_value = brdf_diffuse + brdf_specular * spec_mul;

		float indirect_mul = is_indirect_bounce ? light.indirect_energy : 1.0;

		diffuse_contribution = brdf_diffuse * light.emission * indirect_mul / max(light_select_pdf, 1e-10);
		specular_contribution = brdf_specular * spec_mul * light.emission * indirect_mul / max(light_select_pdf, 1e-10);
		return brdf_value * light.emission * indirect_mul / max(light_select_pdf, 1e-10);
	}
}
