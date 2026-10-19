/**************************************************************************/
/*  dlss.cpp                                                              */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "dlss.h"

#ifdef STREAMLINE_ENABLED
#define ENABLE_DLSS 1
#endif

#ifdef ENABLE_DLSS
#include "core/os/os.h"
#include "drivers/streamline/streamline_context.h"
#include "servers/rendering/renderer_rd/effects/copy_effects.h"
#include "servers/rendering/renderer_rd/storage_rd/material_storage.h"
#include "servers/rendering/renderer_rd/uniform_set_cache_rd.h"
#endif

using namespace RendererRD;

#ifdef ENABLE_DLSS

// Texture layout/state constants (avoid including Vulkan/D3D12 headers here).
static constexpr uint64_t DLSS_VK_IMAGE_LAYOUT_SHADER_READ_ONLY = 5;
static constexpr uint64_t DLSS_D3D12_RESOURCE_STATE_NON_PIXEL_SR = 0x40;
static constexpr float DLSS_OPTIMAL_MODE_MAX_DISTANCE = 1000000.0f;
namespace RendererRD {
class DLSSContextInner : public DLSSContext {
public:
	RID sharpening_output;
	sl::ViewportHandle viewport;
	sl::Constants constants;
	sl::DLSSOptions currentDlssOptions;
	sl::DLSSOptimalSettings currentOptimalSettings;
	sl::DLSSDOptions currentDlssDOptions; // DLSS Ray Reconstruction options
	bool feature_initialized = false;
	bool evaluation_succeeded = false;
	bool ray_reconstruction_active = false;
	bool has_queued_work = false;
	bool sr_resources_used = false;
	bool rr_resources_used = false;
	bool nis_resources_used = false;
	bool camera_initialized = false;
	Projection previous_camera_projection;
	Transform3D previous_camera_transform;

	DLSSContextInner();
	virtual ~DLSSContextInner();

	sl::DLSSMode find_optimal_mode(uint32_t outputWidth, uint32_t outputHeight, uint32_t desiredWidth, uint32_t desiredHeight, sl::DLSSOptimalSettings &out_optimalSettings, bool use_dlss_rr = false) {
		// For DLSS-RR, use the DLSS-D API; for regular DLSS, use the standard DLSS API
		if (use_dlss_rr) {
			if (StreamlineContext::get().slDLSSDGetOptimalSettings == nullptr) {
				return sl::DLSSMode::eOff;
			}
		} else {
			if (StreamlineContext::get().slDLSSGetOptimalSettings == nullptr) {
				return sl::DLSSMode::eOff;
			}
		}

		sl::DLSSMode modes[] = { sl::DLSSMode::eDLAA, sl::DLSSMode::eMaxQuality, sl::DLSSMode::eBalanced, sl::DLSSMode::eMaxPerformance, sl::DLSSMode::eUltraPerformance };
		sl::DLSSOptimalSettings settings[sizeof(modes) / sizeof(modes[0])];
		bool validSettings[sizeof(modes) / sizeof(modes[0])];
		Vector2 distance[sizeof(modes) / sizeof(modes[0])];
		memset(validSettings, 0, sizeof(validSettings));

		for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); i++) {
			sl::Result result;

			if (use_dlss_rr) {
				sl::DLSSDOptions dlssDOptions = {};
				dlssDOptions.outputWidth = outputWidth;
				dlssDOptions.outputHeight = outputHeight;
				dlssDOptions.mode = modes[i];
				sl::DLSSDOptimalSettings dlssDSettings;
				result = StreamlineContext::get().slDLSSDGetOptimalSettings(dlssDOptions, dlssDSettings);
				if (result == sl::Result::eOk) {
					// Copy to common settings struct
					settings[i].optimalRenderWidth = dlssDSettings.optimalRenderWidth;
					settings[i].optimalRenderHeight = dlssDSettings.optimalRenderHeight;
					settings[i].optimalSharpness = dlssDSettings.optimalSharpness;
					settings[i].renderWidthMin = dlssDSettings.renderWidthMin;
					settings[i].renderHeightMin = dlssDSettings.renderHeightMin;
					settings[i].renderWidthMax = dlssDSettings.renderWidthMax;
					settings[i].renderHeightMax = dlssDSettings.renderHeightMax;
				}
			} else {
				sl::DLSSOptions dlssOptions = {};
				dlssOptions.outputWidth = outputWidth;
				dlssOptions.outputHeight = outputHeight;
				dlssOptions.mode = modes[i];
				result = StreamlineContext::get().slDLSSGetOptimalSettings(dlssOptions, settings[i]);
			}

			if (result != sl::Result::eOk) {
				continue;
			}

			sl::DLSSOptimalSettings &optimalSettings = settings[i];
			if (desiredWidth >= optimalSettings.renderWidthMin &&
					desiredWidth <= optimalSettings.renderWidthMax &&
					desiredHeight >= optimalSettings.renderHeightMin &&
					desiredHeight <= optimalSettings.renderHeightMax) {
				validSettings[i] = true;
				distance[i] = Vector2(fabsf((float)optimalSettings.optimalRenderWidth - (float)desiredWidth), fabsf((float)optimalSettings.optimalRenderHeight - (float)desiredHeight));
			}
		}

		// now select the closest match
		Vector2 closestDistance(DLSS_OPTIMAL_MODE_MAX_DISTANCE, DLSS_OPTIMAL_MODE_MAX_DISTANCE);
		int closestDistanceMatch = -1;
		for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); i++) {
			if (validSettings[i]) {
				if (distance[i].length_squared() < closestDistance.length_squared()) {
					closestDistanceMatch = i;
					closestDistance = distance[i];
				}
			}
		}

		if (closestDistanceMatch != -1) {
			out_optimalSettings = settings[closestDistanceMatch];
			return modes[closestDistanceMatch];
		}

		ERR_FAIL_V_MSG(sl::DLSSMode::eOff, "Couldn't find an appropriate DLSS mode.");
	}
}; // end class
}; // end namespace RendererRD

static Vector<unsigned int> g_dlss_freeViewportIndices;
static unsigned int g_dlss_viewportIndex = 1;

DLSSContextInner::~DLSSContextInner() {
	StreamlineContext &sl_context = StreamlineContext::get();
	if (has_queued_work && RD::get_singleton() && sl_context.slShutdown) {
		// A callback holds this context, and the SDK owns resources used by its
		// recorded commands. Finish both before freeing them or recycling the ID.
		RD::get_singleton()->flush_and_wait();
		if (sl_context.dlssg_viewport == viewport) {
			sl_context.dlssg_disable();
		}
		if (sl_context.slFreeResources) {
			for (sl::Feature feature : { sl::kFeatureDLSS, sl::kFeatureDLSS_RR, sl::kFeatureNIS }) {
				if ((feature == sl::kFeatureDLSS && !sr_resources_used) ||
						(feature == sl::kFeatureDLSS_RR && !rr_resources_used) ||
						(feature == sl::kFeatureNIS && !nis_resources_used)) {
					continue;
				}
				sl::Result result = sl_context.slFreeResources(feature, viewport);
				ERR_CONTINUE_MSG(result != sl::Result::eOk, "Cannot release Streamline viewport resources: " + String(StreamlineContext::result_to_string(result)));
			}
		}
	}
	if (sharpening_output.is_valid()) {
		RD::get_singleton()->free_rid(sharpening_output);
	}
	g_dlss_freeViewportIndices.push_back((unsigned int)viewport);
}

DLSSContextInner::DLSSContextInner() {
	if (g_dlss_freeViewportIndices.size() == 0) {
		g_dlss_freeViewportIndices.push_back(g_dlss_viewportIndex++);
	}
	viewport = g_dlss_freeViewportIndices[g_dlss_freeViewportIndices.size() - 1];
	g_dlss_freeViewportIndices.remove_at(g_dlss_freeViewportIndices.size() - 1);
}

DLSSEffect::DLSSEffect() {
	// Initialize motion vector decode shader
	Vector<String> modes;
	modes.push_back("\n");
	shaders.mvec_decode_shader.initialize(modes, "");
	shaders.mvec_decode_version = shaders.mvec_decode_shader.version_create();
	shaders.mvec_decode_pipeline = RD::get_singleton()->compute_pipeline_create(shaders.mvec_decode_shader.version_get_shader(shaders.mvec_decode_version, 0));
}

DLSSEffect::~DLSSEffect() {
	// Deinitialize motion vector decode
	shaders.mvec_decode_shader.version_free(shaders.mvec_decode_version);
}


DLSSContext *DLSSEffect::create_context(Size2i p_internal_size, Size2i p_target_size, bool p_ray_reconstruction) {
	DLSSContextInner *context = memnew(RendererRD::DLSSContextInner);

	context->ray_reconstruction_requested = p_ray_reconstruction;
	const bool query_rr = p_ray_reconstruction && StreamlineContext::get().streamline_capabilities.dlss_rr_available;
	context->currentDlssOptions.mode = context->find_optimal_mode(p_target_size.width, p_target_size.height, p_internal_size.width, p_internal_size.height, context->currentOptimalSettings, query_rr);
	if (OS::get_singleton()->get_environment("GODOT_DLSS_DIAGNOSTICS") == "1") {
		print_line(String("DLSS_OPTIMAL_SETTINGS feature=") + (query_rr ? "RR" : "SR") + " input=" + itos(p_internal_size.width) + "x" + itos(p_internal_size.height) +
				" output=" + itos(p_target_size.width) + "x" + itos(p_target_size.height) + " mode=" + itos(int(context->currentDlssOptions.mode)));
	}
	context->currentDlssOptions.outputWidth = p_target_size.width;
	context->currentDlssOptions.outputHeight = p_target_size.height;

	context->is_d3d12 = (RD::get_singleton()->get_device_api_name().to_lower() == "d3d12");

	return context;
}

static sl::float4x4 sl_make_identity_matrix() {
	sl::float4x4 ret;
	ret.setRow(0, sl::float4(1.0f, 0.0f, 0.0f, 0.0f));
	ret.setRow(1, sl::float4(0.0f, 1.0f, 0.0f, 0.0f));
	ret.setRow(2, sl::float4(0.0f, 0.0f, 1.0f, 0.0f));
	ret.setRow(3, sl::float4(0.0f, 0.0f, 0.0f, 1.0f));
	return ret;
}

static sl::float4x4 sl_convert_matrix(const Projection &mtx) {
	// Godot transforms column vectors; Streamline transforms row vectors (see
	// sl_matrix_helpers.h). Transpose the mathematical transform as well as
	// using row-major storage: each Godot column becomes a Streamline row.
	// In particular, affine translation must occupy Streamline's final row.
	sl::float4x4 ret;
	ret.setRow(0, sl::float4(mtx.columns[0].x, mtx.columns[0].y, mtx.columns[0].z, mtx.columns[0].w));
	ret.setRow(1, sl::float4(mtx.columns[1].x, mtx.columns[1].y, mtx.columns[1].z, mtx.columns[1].w));
	ret.setRow(2, sl::float4(mtx.columns[2].x, mtx.columns[2].y, mtx.columns[2].z, mtx.columns[2].w));
	ret.setRow(3, sl::float4(mtx.columns[3].x, mtx.columns[3].y, mtx.columns[3].z, mtx.columns[3].w));
	return ret;
}

static sl::float3 sl_convert_vector(const Vector3 &vec) {
	return sl::float3(vec.x, vec.y, vec.z);
}

void DLSSEffect::upscale(const DLSSContext::Parameters &p_params) {
	DLSSContextInner *context = (DLSSContextInner *)p_params.context;

	// Delay enablement
	if (context->delay > 0) {
		--context->delay;
		const RD::TextureFormat output_format = RD::get_singleton()->texture_get_format(p_params.output);
		CopyEffects::get_singleton()->copy_to_rect(p_params.color, p_params.output, Rect2i(0, 0, output_format.width, output_format.height), false, false, true);
		return;
	}

	// If DLSS is not loaded, escape early
	if (StreamlineContext::get().slDLSSSetOptions == nullptr) {
		return;
	}

	// Constants and evaluation must use the token captured for this draw.
	sl::FrameToken *frame_token = StreamlineContext::get().get_current_frame_token();
	if (frame_token == nullptr) {
		return;
	}

	context->last_parameters = p_params;
	context->last_parameters.frame_token = frame_token;
	context->last_effect = this;

	// Decode mvecs
	{
		RD::get_singleton()->draw_command_begin_label("Decode Invalid Motion Vectors");
		UniformSetCacheRD *uniform_set_cache = UniformSetCacheRD::get_singleton();
		ERR_FAIL_NULL(uniform_set_cache);
		MaterialStorage *material_storage = MaterialStorage::get_singleton();
		ERR_FAIL_NULL(material_storage);

		// setup our uniforms
		RD::Uniform u_velocity_image(RD::UNIFORM_TYPE_IMAGE, 0, p_params.velocity);
		RD::Uniform u_depth_texture(RD::UNIFORM_TYPE_TEXTURE, 0, p_params.depth);

		RD::ComputeListID compute_list = RD::get_singleton()->compute_list_begin();

		RID shader = shaders.mvec_decode_shader.version_get_shader(shaders.mvec_decode_version, 0);
		ERR_FAIL_COND(shader.is_null());

		RD::get_singleton()->compute_list_bind_compute_pipeline(compute_list, shaders.mvec_decode_pipeline);
		RD::get_singleton()->compute_list_bind_uniform_set(compute_list, uniform_set_cache->get_cache(shader, 0, u_velocity_image), 0);
		RD::get_singleton()->compute_list_bind_uniform_set(compute_list, uniform_set_cache->get_cache(shader, 1, u_depth_texture), 1);

		auto texture_format = RD::get_singleton()->texture_get_format(p_params.velocity);

		float push_constants[20];
		push_constants[0] = texture_format.width;
		push_constants[1] = texture_format.height;
		push_constants[2] = 0.0f;
		push_constants[3] = 0.0f;
		memcpy(push_constants + 4, &p_params.reprojection.columns[0].x, sizeof(float) * 16);
		RD::get_singleton()->compute_list_set_push_constant(compute_list, push_constants, sizeof(push_constants));

		RD::get_singleton()->compute_list_dispatch_threads(compute_list, texture_format.width, texture_format.height, 1);
		RD::get_singleton()->compute_list_add_barrier(compute_list);

		RD::get_singleton()->compute_list_end();
		RD::get_singleton()->draw_command_end_label();
	}


	// Inject DLSS into the render graph
	RD::CallbackResource res[11]; // Includes separate transparency color/opacity.
	int num_resources = 0;
	res[num_resources++].rid = p_params.color;
	res[num_resources++].rid = p_params.output;
	res[num_resources++].rid = p_params.depth;
	res[num_resources++].rid = p_params.velocity;

	// Add DLSS-RR buffers if provided
	if (p_params.dlss_rr) {
		if (p_params.dlss_rr_diffuse_albedo.is_valid()) {
			res[num_resources++].rid = p_params.dlss_rr_diffuse_albedo;
		}
		if (p_params.dlss_rr_specular_albedo.is_valid()) {
			res[num_resources++].rid = p_params.dlss_rr_specular_albedo;
		}
		if (p_params.dlss_rr_normal_roughness.is_valid()) {
			res[num_resources++].rid = p_params.dlss_rr_normal_roughness;
		}
		if (p_params.dlss_rr_specular_hit_dist.is_valid()) {
			res[num_resources++].rid = p_params.dlss_rr_specular_hit_dist;
		}
		if (p_params.dlss_rr_color_before_transparency.is_valid() && p_params.dlss_rr_color_before_transparency != p_params.color) {
			res[num_resources++].rid = p_params.dlss_rr_color_before_transparency;
		}
	}

	for (int i = 0; i < num_resources; i++) {
		res[i].usage = RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE;
	}
	// DLSS writes the output; expose that dependency to the render graph.
	res[1].usage = RD::CALLBACK_RESOURCE_USAGE_GENERAL; // SDK may also transfer-clear during reset.
	context->has_queued_work = true;
	RD::get_singleton()->driver_callback_add((RDD::DriverCallback)DLSSEffect::_upscale_internal_graph_callback, p_params.context, VectorView<RD::CallbackResource>(res, num_resources));
	if (p_params.sharpness > 0.0f && StreamlineContext::get().slNISSetOptions != nullptr && StreamlineContext::get().streamline_capabilities.nis_available) {
		RD *rd = RD::get_singleton();
		RD::TextureFormat format = rd->texture_get_format(p_params.output);
		// Streamline 2.10 NIS declares its Vulkan storage output as rgba32f.
		format.format = RD::DATA_FORMAT_R32G32B32A32_SFLOAT;
		if (context->sharpening_output.is_valid()) {
			RD::TextureFormat previous = rd->texture_get_format(context->sharpening_output);
			if (previous.width != format.width || previous.height != format.height || previous.format != format.format) {
				rd->free_rid(context->sharpening_output);
				context->sharpening_output = RID();
			}
		}
		if (context->sharpening_output.is_null()) {
			format.usage_bits = RD::TEXTURE_USAGE_SAMPLING_BIT | RD::TEXTURE_USAGE_STORAGE_BIT;
			context->sharpening_output = rd->texture_create(format, RD::TextureView());
		}
		ERR_FAIL_COND(context->sharpening_output.is_null());
		// Use a separate correctly typed output, then convert to the renderer's
		// native color format through a tracked shader copy. No implicit SDK clone.
		RD::CallbackResource sharpen_resources[2];
		sharpen_resources[0].rid = p_params.output;
		sharpen_resources[0].usage = RD::CALLBACK_RESOURCE_USAGE_TEXTURE_SAMPLE;
		sharpen_resources[1].rid = context->sharpening_output;
		sharpen_resources[1].usage = RD::CALLBACK_RESOURCE_USAGE_STORAGE_IMAGE_READ_WRITE;
		rd->driver_callback_add((RDD::DriverCallback)DLSSEffect::_sharpen_internal_graph_callback, context, VectorView<RD::CallbackResource>(sharpen_resources, 2));
		CopyEffects::get_singleton()->copy_to_rect(context->sharpening_output, p_params.output, Rect2i(0, 0, format.width, format.height));
	}
}

void DLSSEffect::_upscale_internal(RDD::CommandBufferID cmdid, const DLSSContext::Parameters &p_params, bool p_sharpen_only) {
	sl::FrameToken *frame_token = static_cast<sl::FrameToken *>(p_params.frame_token);
	ERR_FAIL_NULL(frame_token);
	DLSSContextInner *context = (DLSSContextInner *)p_params.context;

	void *nativeCmdlist = RD::get_singleton()->get_device_driver()->command_buffer_get_native_handle(cmdid);

	// Helper function for tagging resources.
	auto assignResource = [context, &p_params, p_sharpen_only](sl::Resource *resources, sl::ResourceTag *resourceTags, int &numResources, RID textureRID, sl::BufferType bufferType, sl::ResourceLifecycle lifecycle) {
		if (!textureRID.is_valid() || textureRID.is_null()) {
			return;
		}

		RD::TextureFormat texture_format = RD::get_singleton()->texture_get_format(textureRID);
		uint64_t texture_image = RD::get_singleton()->get_driver_resource(RD::DriverResource::DRIVER_RESOURCE_TEXTURE, textureRID);
		uint64_t texture_view = RD::get_singleton()->get_driver_resource(RD::DriverResource::DRIVER_RESOURCE_TEXTURE_VIEW, textureRID);
		uint64_t texture_device_memory = RD::get_singleton()->get_driver_resource(RD::DriverResource::DRIVER_RESOURCE_TEXTURE_DEVICE_MEMORY, textureRID);
		const bool is_output = p_sharpen_only ? textureRID == context->sharpening_output : textureRID == p_params.output;
		uint64_t texture_state = is_output ? 1 : DLSS_VK_IMAGE_LAYOUT_SHADER_READ_ONLY; // GENERAL for the storage output.
		if (context->is_d3d12) {
			texture_state = is_output ? 0x8 : DLSS_D3D12_RESOURCE_STATE_NON_PIXEL_SR; // UNORDERED_ACCESS for output.
		}
		uint64_t texture_vkformat = RD::get_singleton()->get_driver_resource(RD::DriverResource::DRIVER_RESOURCE_TEXTURE_DATA_FORMAT, textureRID);
		uint64_t texture_usage_flags = RD::get_singleton()->get_driver_resource(RD::DriverResource::DRIVER_RESOURCE_TEXTURE_USAGE_FLAGS, textureRID);
		auto &destinationResource = resources[numResources];
		if (context->is_d3d12) {
			destinationResource = sl::Resource(sl::ResourceType::eTex2d,
					(void *)texture_view, texture_state);
		} else {
			destinationResource = sl::Resource(sl::ResourceType::eTex2d,
					(void *)texture_image, (void *)texture_device_memory, (void *)texture_view, texture_state);
		}
		destinationResource.width = texture_format.width;
		destinationResource.height = texture_format.height;
		destinationResource.nativeFormat = texture_vkformat;
		destinationResource.arrayLayers = texture_format.array_layers;
		destinationResource.flags = 0;
		destinationResource.mipLevels = texture_format.mipmaps;
		destinationResource.usage = texture_usage_flags;

		resourceTags[numResources] = sl::ResourceTag(resources + numResources, bufferType, lifecycle, nullptr);
		++numResources;
	};

	if (!p_sharpen_only) {
		context->evaluation_succeeded = false;
		// Set DLSS or DLSS-RR options depending on mode
		bool use_dlss_rr = p_params.dlss_rr && StreamlineContext::get().slDLSSDSetOptions != nullptr && StreamlineContext::get().streamline_capabilities.dlss_rr_available;
		const bool feature_changed = !context->feature_initialized || context->ray_reconstruction_active != use_dlss_rr;
		if (feature_changed && !context->is_d3d12 && OS::get_singleton()->is_stdout_verbose()) {
			// Identify application-owned images when comparing opaque SDK validation
			// messages against its inputs. Do not log this on every evaluation.
			String handles = "Streamline image handles (hex):";
			const RID textures[] = { p_params.color, p_params.output, p_params.depth, p_params.velocity };
			for (RID texture : textures) {
				handles += " " + String::num_uint64(RD::get_singleton()->get_driver_resource(RD::DRIVER_RESOURCE_TEXTURE, texture), 16);
			}
			print_verbose(handles + " (color, output, depth, velocity)");
		}
		if (feature_changed) {
			// SR and Ray Reconstruction have independent per-viewport options.
			// Selecting one does not disable the other Streamline feature.
			sl::Result result = sl::Result::eOk;
			if (use_dlss_rr && StreamlineContext::get().slDLSSSetOptions && StreamlineContext::get().streamline_capabilities.dlss_available) {
				sl::DLSSOptions disabled;
				disabled.mode = sl::DLSSMode::eOff;
				result = StreamlineContext::get().slDLSSSetOptions(context->viewport, disabled);
			} else if (!use_dlss_rr && StreamlineContext::get().slDLSSDSetOptions && StreamlineContext::get().streamline_capabilities.dlss_rr_available) {
				sl::DLSSDOptions disabled;
				disabled.mode = sl::DLSSMode::eOff;
				result = StreamlineContext::get().slDLSSDSetOptions(context->viewport, disabled);
			}
			ERR_FAIL_COND_MSG(result != sl::Result::eOk, "Cannot disable the previous Streamline reconstruction feature: " + String(StreamlineContext::result_to_string(result)));
			context->feature_initialized = true;
			context->ray_reconstruction_active = use_dlss_rr;
		}

		if (use_dlss_rr) {
			// Set DLSS-RR (Ray Reconstruction) options
			context->currentDlssDOptions.mode = context->currentDlssOptions.mode;
			context->currentDlssDOptions.outputWidth = context->currentDlssOptions.outputWidth;
			context->currentDlssDOptions.outputHeight = context->currentDlssOptions.outputHeight;
			context->currentDlssDOptions.colorBuffersHDR = sl::Boolean::eTrue;
			context->currentDlssDOptions.alphaUpscalingEnabled = p_params.dlss_rr_alpha_upscaling ? sl::Boolean::eTrue : sl::Boolean::eFalse;
			context->currentDlssDOptions.normalRoughnessMode = sl::DLSSDNormalRoughnessMode::ePacked; // Normal XYZ + Roughness W

			// Set world-to-camera and camera-to-world matrices for DLSS-RR
			// worldToCameraView = view matrix (world-to-camera transformation)
			// cameraViewToWorld = inverse view matrix (camera-to-world transformation)
			Transform3D view_matrix = p_params.cam_transform.affine_inverse();
			context->currentDlssDOptions.worldToCameraView = sl_convert_matrix(Projection(view_matrix)); //
			context->currentDlssDOptions.cameraViewToWorld = sl_convert_matrix(Projection(view_matrix).inverse());
			char dlssPreset = p_params.preset;
			if (dlssPreset == '?') {
				dlssPreset = StreamlineContext::get().dlss_rr_default_preset;
			}

			if (dlssPreset == '?') {
				context->currentDlssDOptions.dlaaPreset = sl::DLSSDPreset::eDefault;
				context->currentDlssDOptions.qualityPreset = sl::DLSSDPreset::eDefault;
				context->currentDlssDOptions.balancedPreset = sl::DLSSDPreset::eDefault;
				context->currentDlssDOptions.performancePreset = sl::DLSSDPreset::eDefault;
				context->currentDlssDOptions.ultraPerformancePreset = sl::DLSSDPreset::eDefault;
			} else {
				int presetNo = ((int)dlssPreset - (int)'D');
				sl::DLSSDPreset preset = (sl::DLSSDPreset)((int)sl::DLSSDPreset::ePresetD + presetNo);
				context->currentDlssDOptions.dlaaPreset = preset;
				context->currentDlssDOptions.qualityPreset = preset;
				context->currentDlssDOptions.balancedPreset = preset;
				context->currentDlssDOptions.performancePreset = preset;
				context->currentDlssDOptions.ultraPerformancePreset = preset;
			}

			sl::Result result = StreamlineContext::get().slDLSSDSetOptions(context->viewport, context->currentDlssDOptions);
			if (result != sl::Result::eOk) {
				ERR_FAIL_MSG("Failed to call streamline slDLSSDSetOptions. Result: " + String(StreamlineContext::result_to_string(result)));
			}
		} else if (StreamlineContext::get().slDLSSSetOptions != nullptr && StreamlineContext::get().streamline_capabilities.dlss_available) {
			// Set regular DLSS options
			// Godot's luminance-reduction buffer stores luminance, not the exposure
			// multiplier required by Streamline. Let DLSS derive exposure from HDR
			// color instead of disabling auto-exposure without a valid exposure tag.
			context->currentDlssOptions.useAutoExposure = sl::Boolean::eTrue;

			context->currentDlssOptions.colorBuffersHDR = sl::Boolean::eTrue;
			char dlssPreset = p_params.preset;
			if (dlssPreset == '?') {
				dlssPreset = StreamlineContext::get().dlss_default_preset;
			}

			if (dlssPreset == '?') {
				context->currentDlssOptions.dlaaPreset = sl::DLSSPreset::eDefault;
				context->currentDlssOptions.qualityPreset = sl::DLSSPreset::eDefault;
				context->currentDlssOptions.balancedPreset = sl::DLSSPreset::eDefault;
				context->currentDlssOptions.performancePreset = sl::DLSSPreset::eDefault;
				context->currentDlssOptions.ultraPerformancePreset = sl::DLSSPreset::eDefault;
			} else {
				int presetNo = ((int)dlssPreset - (int)'F');
				sl::DLSSPreset preset = (sl::DLSSPreset)((int)sl::DLSSPreset::ePresetF + presetNo);
				context->currentDlssOptions.dlaaPreset = preset;
				context->currentDlssOptions.qualityPreset = preset;
				context->currentDlssOptions.balancedPreset = preset;
				context->currentDlssOptions.performancePreset = preset;
				context->currentDlssOptions.ultraPerformancePreset = preset;
			}

			sl::Result result = StreamlineContext::get().slDLSSSetOptions(context->viewport, context->currentDlssOptions);
			if (result != sl::Result::eOk) {
				ERR_FAIL_MSG("Failed to call streamline slDLSSSetOptions. Result: " + String(StreamlineContext::result_to_string(result)));
			}
		}

		// Set SL Options
		if (StreamlineContext::get().slSetConstants != nullptr) {
			sl::float4x4 mtxIdentity = sl_make_identity_matrix();
			// Guide projection must match the tagged hardware depth: flipped Y,
			// reversed Z in [0, 1], with no jitter. Godot's camera projection is
			// still in OpenGL [-1, 1] depth space at this point.
			Projection guide_correction;
			guide_correction.set_depth_correction(true, p_params.reverse_depth, true);
			const Projection guide_projection = guide_correction * p_params.cam_projection;
			// The motion decoder consumes depth * 2 - 1, so its reprojection uses
			// [-1, 1]. Streamline consumes hardware [0, 1] depth instead.
			Projection clip_depth_remap;
			clip_depth_remap.set_depth_correction(false, false, true);
			const Projection guide_reprojection = clip_depth_remap * p_params.reprojection * clip_depth_remap.inverse();
			context->constants.cameraViewToClip = sl_convert_matrix(guide_projection);
			context->constants.clipToCameraView = sl_convert_matrix(guide_projection.inverse());
			context->constants.clipToLensClip = mtxIdentity; // keep identity unless some lens distortion is applied
			context->constants.clipToPrevClip = sl_convert_matrix(guide_reprojection);
			context->constants.prevClipToClip = sl_convert_matrix(guide_reprojection.inverse());

			context->constants.cameraPos = sl_convert_vector(p_params.cam_transform.get_origin());
			context->constants.cameraFwd = sl_convert_vector(-p_params.cam_transform.get_basis().get_column(2));
			context->constants.cameraUp = sl_convert_vector(p_params.cam_transform.get_basis().get_column(1));
			context->constants.cameraRight = sl_convert_vector(p_params.cam_transform.get_basis().get_column(0));

			context->constants.cameraNear = p_params.z_near;
			context->constants.cameraFar = p_params.z_far;
			context->constants.cameraFOV = Math::deg_to_rad(p_params.fovy);
			if (feature_changed) {
				print_verbose("DLSS camera vertical FOV: " + rtos(p_params.fovy) + " degrees.");
			}
			context->constants.cameraMotionIncluded = sl::Boolean::eTrue;
			context->constants.cameraAspectRatio = static_cast<float>(context->currentDlssOptions.outputWidth) / static_cast<float>(context->currentDlssOptions.outputHeight);
			context->constants.cameraPinholeOffset = sl::float2(0.0f, 0.0f);
			context->constants.depthInverted = p_params.reverse_depth ? sl::Boolean::eTrue : sl::Boolean::eFalse;
			context->constants.motionVectors3D = sl::Boolean::eFalse;
			context->constants.motionVectorsDilated = sl::Boolean::eFalse;
			context->constants.motionVectorsJittered = sl::Boolean::eFalse;
			context->constants.jitterOffset = sl::float2(p_params.jitter.x, p_params.jitter.y);
			context->constants.mvecScale = sl::float2(1.0f, 1.0f);
			context->constants.orthographicProjection = p_params.cam_projection.is_orthogonal() ? sl::Boolean::eTrue : sl::Boolean::eFalse;
			// A camera switch can reset the renderer's previous camera to the new
			// view. Detect that discontinuity against the last evaluated view too.
			const bool camera_discontinuity = !context->camera_initialized ||
					!context->previous_camera_transform.is_equal_approx(p_params.prev_cam_transform) ||
					context->previous_camera_projection != p_params.prev_cam_projection;
			context->constants.reset = (p_params.reset_accumulation || feature_changed || camera_discontinuity) ? sl::Boolean::eTrue : sl::Boolean::eFalse;
			if (context->constants.reset == sl::Boolean::eTrue) {
				print_verbose("DLSS history reset: feature=" + itos(feature_changed) + " camera=" + itos(camera_discontinuity) + " requested=" + itos(p_params.reset_accumulation));
			}
			sl::Result result = StreamlineContext::get().slSetConstants(context->constants, *frame_token, context->viewport);
			if (result != sl::Result::eOk) {
				ERR_FAIL_MSG("Failed to call streamline slSetConstants. Result: " + String(StreamlineContext::result_to_string(result)));
			}
		}

		// Tag resources
		if (StreamlineContext::get().slSetTag != nullptr) {
			sl::Resource resources[12];
			sl::ResourceTag resourceTags[12];
			int numResources = 0;
			// SR/RR evaluate immediately in this callback. Later passes can modify
			// these textures, so do not promise unchanged contents until present.
			const sl::ResourceLifecycle lifecycle = p_params.dlss_g ? sl::ResourceLifecycle::eValidUntilPresent : sl::ResourceLifecycle::eValidUntilEvaluate;

			assignResource(resources, resourceTags, numResources, p_params.color, sl::kBufferTypeScalingInputColor, lifecycle);
			assignResource(resources, resourceTags, numResources, p_params.output, sl::kBufferTypeScalingOutputColor, lifecycle);
			assignResource(resources, resourceTags, numResources, p_params.depth, sl::kBufferTypeDepth, lifecycle);
			assignResource(resources, resourceTags, numResources, p_params.velocity, sl::kBufferTypeMotionVectors, lifecycle);

			// Tag DLSS-RR specific buffers if enabled
			if (use_dlss_rr) {
				// kBufferTypeAlbedo is used for diffuse albedo
				assignResource(resources, resourceTags, numResources, p_params.dlss_rr_diffuse_albedo, sl::kBufferTypeAlbedo, lifecycle);
				assignResource(resources, resourceTags, numResources, p_params.dlss_rr_specular_albedo, sl::kBufferTypeSpecularAlbedo, lifecycle);
				// kBufferTypeNormalRoughness for packed normal+roughness (XYZ=normal, W=roughness)
				assignResource(resources, resourceTags, numResources, p_params.dlss_rr_normal_roughness, sl::kBufferTypeNormalRoughness, lifecycle);
				assignResource(resources, resourceTags, numResources, p_params.dlss_rr_specular_hit_dist, sl::kBufferTypeSpecularHitDistance, lifecycle);
				assignResource(resources, resourceTags, numResources, p_params.dlss_rr_color_before_transparency, sl::kBufferTypeColorBeforeTransparency, lifecycle);
			}

			sl::Result result = StreamlineContext::get().frame_based_resource_tagging ? StreamlineContext::get().slSetTagForFrame(*frame_token, context->viewport, resourceTags, numResources, nativeCmdlist) : StreamlineContext::get().slSetTag(context->viewport, resourceTags, numResources, nativeCmdlist);
			if (result != sl::Result::eOk) {
				ERR_FAIL_MSG("Failed to call streamline slSetTag. Result: " + String(StreamlineContext::result_to_string(result)));
			}
		}

		// Toggle DLSS Frame Generation (only enabled in game mode)
		if (StreamlineContext::get().slDLSSGSetOptions != nullptr && StreamlineContext::get().is_game && StreamlineContext::get().streamline_capabilities.dlss_g_available) {
			sl::DLSSGOptions dlssGOptions{};
			bool wantActivateDLSSG = p_params.dlss_g;
			bool canActivateDLSSG = StreamlineContext::get().dlssg_delay == 0;

			// Disable previous DLSS-G context if needed
			if (StreamlineContext::get().dlssg_viewport != sl::ViewportHandle(-1) && ((!wantActivateDLSSG && StreamlineContext::get().dlssg_viewport == context->viewport) || (wantActivateDLSSG && StreamlineContext::get().dlssg_viewport != context->viewport))) {
				WARN_PRINT("Disabling DLSS-G on viewport: " + itos((unsigned int)StreamlineContext::get().dlssg_viewport));
				dlssGOptions.mode = sl::DLSSGMode::eOff;
				sl::Result result = StreamlineContext::get().slDLSSGSetOptions(StreamlineContext::get().dlssg_viewport, dlssGOptions);
				if (result != sl::Result::eOk) {
					ERR_FAIL_MSG("Failed to call streamline slDLSSGSetOptions. Result: " + String(StreamlineContext::result_to_string(result)));
				}

				StreamlineContext::get().dlssg_viewport = sl::ViewportHandle(-1);
			}

			// Enable new DLSS-G context if needed
			if (canActivateDLSSG && wantActivateDLSSG && StreamlineContext::get().dlssg_viewport != context->viewport) {
				WARN_PRINT("Enabling DLSS-G on viewport: " + itos((unsigned int)context->viewport));

				dlssGOptions.mode = sl::DLSSGMode::eOn;
				sl::Result result = StreamlineContext::get().slDLSSGSetOptions(context->viewport, dlssGOptions);
				if (result != sl::Result::eOk) {
					ERR_FAIL_MSG("Failed to call streamline slDLSSGSetOptions. Result: " + String(StreamlineContext::result_to_string(result)));
				}

				StreamlineContext::get().dlssg_viewport = context->viewport;
			}
		}

		// Evaluate DLSS Super Resolution or DLSS Ray Reconstruction
		if (context->currentDlssOptions.mode != sl::DLSSMode::eOff) {
			const sl::BaseStructure *inputs[] = { &context->viewport };
			sl::Result result;

			if (use_dlss_rr && StreamlineContext::get().streamline_capabilities.dlss_rr_available) {
				// Use DLSS Ray Reconstruction
				const bool first_evaluation = !context->rr_resources_used;
				context->rr_resources_used = true;
				result = StreamlineContext::get().slEvaluateFeature(sl::kFeatureDLSS_RR, *frame_token, inputs, 1, nativeCmdlist);
				if (result != sl::Result::eOk) {
					ERR_FAIL_MSG("Failed to call streamline slEvaluateFeature for DLSS Ray Reconstruction. Result: " + String(StreamlineContext::result_to_string(result)));
				}
				context->ray_reconstruction_evaluations.increment();
				if (first_evaluation && OS::get_singleton()->get_environment("GODOT_DLSS_DIAGNOSTICS") == "1") {
					print_line("DLSS_EVALUATION feature=RR succeeded=1");
				}
				if (context->constants.reset == sl::Boolean::eTrue) {
					context->ray_reconstruction_resets.increment();
				}
			} else if (StreamlineContext::get().streamline_capabilities.dlss_available) {
				// Use regular DLSS
				const bool first_evaluation = !context->sr_resources_used;
				context->sr_resources_used = true;
				result = StreamlineContext::get().slEvaluateFeature(sl::kFeatureDLSS, *frame_token, inputs, 1, nativeCmdlist);
				if (result != sl::Result::eOk) {
					ERR_FAIL_MSG("Failed to call streamline slEvaluateFeature for DLSS Super Resolution. Result: " + String(StreamlineContext::result_to_string(result)));
				}
				context->super_resolution_evaluations.increment();
				if (context->constants.reset == sl::Boolean::eTrue) {
					context->super_resolution_resets.increment();
				}
				if (first_evaluation && OS::get_singleton()->get_environment("GODOT_DLSS_DIAGNOSTICS") == "1") {
					print_line("DLSS_EVALUATION feature=SR succeeded=1");
				}
			}
			context->camera_initialized = true;
			context->evaluation_succeeded = true;
			context->previous_camera_projection = p_params.cam_projection;
			context->previous_camera_transform = p_params.cam_transform;
		}

		return;
	}

	// NIS support
	// **********
	if (p_params.sharpness > 0.0f && StreamlineContext::get().slNISSetOptions != nullptr && StreamlineContext::get().streamline_capabilities.nis_available) {
		{ // Set NIS settings
			sl::NISOptions options;
			options.hdrMode = sl::NISHDR::eLinear;
			options.mode = sl::NISMode::eSharpen;
			options.sharpness = p_params.sharpness;
			StreamlineContext::get().slNISSetOptions(context->viewport, options);
		}

		{ // Tag NIS buffers
			sl::Resource resources[3];
			sl::ResourceTag resourceTags[3];
			int numResources = 0;

			assignResource(resources, resourceTags, numResources, p_params.output, sl::kBufferTypeScalingInputColor, sl::ResourceLifecycle::eValidUntilEvaluate);
			assignResource(resources, resourceTags, numResources, context->sharpening_output, sl::kBufferTypeScalingOutputColor, sl::ResourceLifecycle::eValidUntilEvaluate);

			sl::Result result = StreamlineContext::get().frame_based_resource_tagging ? StreamlineContext::get().slSetTagForFrame(*frame_token, context->viewport, resourceTags, numResources, nativeCmdlist) : StreamlineContext::get().slSetTag(context->viewport, resourceTags, numResources, nativeCmdlist);
			if (result != sl::Result::eOk) {
				ERR_FAIL_MSG("Failed to call streamline slSetTag for NIS. Result: " + String(StreamlineContext::result_to_string(result)));
			}
		}

		{ // Evaluate NIS
			const sl::BaseStructure *inputs[] = { &context->viewport };
			context->nis_resources_used = true;
			sl::Result result = StreamlineContext::get().slEvaluateFeature(sl::kFeatureNIS, *frame_token, inputs, 1, nativeCmdlist);
			if (result != sl::Result::eOk) {
				ERR_FAIL_MSG("Failed to call streamline slEvaluateFeature for NIS. Result: " + String(StreamlineContext::result_to_string(result)));
			}
		}
	}
}

void DLSSEffect::_sharpen_internal_graph_callback(RenderingDeviceDriver *p_driver, RDD::CommandBufferID p_command_buffer, void *p_userdata) {
	DLSSContextInner *self = (DLSSContextInner *)p_userdata;
	self->last_effect->_upscale_internal(p_command_buffer, self->last_parameters, true);
}

void RendererRD::DLSSEffect::_upscale_internal_graph_callback(RenderingDeviceDriver *p_driver, RDD::CommandBufferID p_command_buffer, void *p_userdata) {
	DLSSContextInner *self = (DLSSContextInner *)p_userdata;
	self->last_effect->_upscale_internal(p_command_buffer, self->last_parameters);
}

bool DLSSEffect::is_ready(DLSSContext *p_context) {
	DLSSContextInner *context = (DLSSContextInner *)p_context;
	if (context->currentDlssOptions.mode == sl::DLSSMode::eOff) {
		return false; // unsupported mode.
	}
	if (context->delay > 0) {
		return false; // still in delay mode
	}
	return context->evaluation_succeeded;
}
#else
DLSSEffect::DLSSEffect() {}
DLSSEffect::~DLSSEffect() {}
DLSSContext *DLSSEffect::create_context(Size2i p_internal_size, Size2i p_target_size, bool p_ray_reconstruction) {
	return nullptr;
}
void DLSSEffect::upscale(const DLSSContext::Parameters &p_params) {}
bool DLSSEffect::is_ready(DLSSContext *p_context) {
	return false;
}
void DLSSEffect::_upscale_internal(RDD::CommandBufferID cmdid, const DLSSContext::Parameters &p_params, bool p_sharpen_only) {}
void DLSSEffect::_sharpen_internal_graph_callback(RenderingDeviceDriver *p_driver, RDD::CommandBufferID p_command_buffer, void *p_userdata) {}
void DLSSEffect::_upscale_internal_graph_callback(RenderingDeviceDriver *p_driver, RDD::CommandBufferID p_command_buffer, void *p_userdata) {}
#endif
