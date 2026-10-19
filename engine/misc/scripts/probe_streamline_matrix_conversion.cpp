// Standalone convention test using the SDK's actual float4x4 and inverse helper.
// conversion_under_test.h contains the exact helper extracted from dlss.cpp.
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>

#include "sl_matrix_helpers.h"

// Minimal field-compatible input: Godot Projection stores four columns.
// This test exercises the production converter's exact source without linking
// the renderer or needing a GPU. Golden results describe geometric operations.
struct Projection {
	sl::float4 columns[4];
};

#include "conversion_under_test.h"

static sl::float4 row_transform(const sl::float4 &p, const sl::float4x4 &m) {
	return sl::float4(
			p.x * m[0].x + p.y * m[1].x + p.z * m[2].x + p.w * m[3].x,
			p.x * m[0].y + p.y * m[1].y + p.z * m[2].y + p.w * m[3].y,
			p.x * m[0].z + p.y * m[1].z + p.z * m[2].z + p.w * m[3].z,
			p.x * m[0].w + p.y * m[1].w + p.z * m[2].w + p.w * m[3].w);
}

static float error(const sl::float4 &a, const sl::float4 &b) {
	return std::max({ std::abs(a.x - b.x), std::abs(a.y - b.y), std::abs(a.z - b.z), std::abs(a.w - b.w) });
}

int main() {
	Projection view = { { sl::float4(1, 0, 0, 0), sl::float4(0, 1, 0, 0), sl::float4(0, 0, 1, 0), sl::float4(-1, -2, -3, 1) } };
	sl::float4x4 converted_view = sl_convert_matrix(view);
	float origin_error = error(row_transform(sl::float4(1, 2, 3, 1), converted_view), sl::float4(0, 0, 0, 1));
	sl::float4x4 inverse;
	sl::matrixOrthoNormalInvert(inverse, converted_view);
	float inverse_error = error(row_transform(sl::float4(0, 0, 0, 1), inverse), sl::float4(1, 2, 3, 1));

	const float a = .1f / (100.0f - .1f);
	const float b = 100.0f * a;
	Projection projection = { { sl::float4(.9f, 0, 0, 0), sl::float4(0, -1.3f, 0, 0), sl::float4(0, 0, a, -1), sl::float4(0, 0, b, 0) } };
	sl::float4 clip = row_transform(sl::float4(.2f, -.3f, -5.0f, 1), sl_convert_matrix(projection));
	sl::float4 ndc(clip.x / clip.w, clip.y / clip.w, clip.z / clip.w, 1);
	float projection_error = error(ndc, sl::float4(.2f * .9f / 5.0f, .3f * 1.3f / 5.0f, (-5.0f * a + b) / 5.0f, 1));
	bool passed = std::max({ origin_error, inverse_error, projection_error }) < 1e-5f;
	std::cout << std::setprecision(9) << "{\"passed\":" << (passed ? "true" : "false")
			  << ",\"camera_origin_error\":" << origin_error << ",\"sdk_inverse_error\":" << inverse_error
			  << ",\"projection_error\":" << projection_error << ",\"tolerance\":0.00001}\n";
	return passed ? 0 : 7;
}
