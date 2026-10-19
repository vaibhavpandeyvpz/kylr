/**************************************************************************/
/*  rt_light_sampling.h                                                   */
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

#pragma once

#include <cmath>
#include <cstdint>

namespace RTLightSampling {

constexpr uint32_t MAX_LIGHTS = 64;

struct AliasEntry {
	float source_pdf = 0.0f;
	float probability = 0.0f;
	uint32_t alias = 0;
};

// Bounded, allocation-free power/uniform mixture. The uniform component keeps
// every light reachable even if its power estimate is zero or underflows.
// Invalid input leaves the caller's output untouched so enumeration can remain
// active. No renderer resources or application assumptions belong here.
inline bool build_alias_table(const double *p_weights, uint32_t p_count, AliasEntry *r_entries) {
	if (!p_weights || !r_entries || p_count == 0 || p_count > MAX_LIGHTS) {
		return false;
	}
	double maximum = 0.0;
	for (uint32_t i = 0; i < p_count; i++) {
		if (!std::isfinite(p_weights[i]) || p_weights[i] < 0.0) {
			return false;
		}
		maximum = p_weights[i] > maximum ? p_weights[i] : maximum;
	}
	double total = 0.0;
	if (maximum > 0.0) {
		for (uint32_t i = 0; i < p_count; i++) {
			total += p_weights[i] / maximum;
		}
	}
	double scaled[MAX_LIGHTS] = {};
	uint32_t small[MAX_LIGHTS], large[MAX_LIGHTS];
	uint32_t small_count = 0, large_count = 0;
	AliasEntry entries[MAX_LIGHTS];
	for (uint32_t i = 0; i < p_count; i++) {
		scaled[i] = total > 0.0 ? 0.9 * (p_weights[i] / maximum) / total * p_count + 0.1 : 1.0;
		if (scaled[i] < 1.0) {
			small[small_count++] = i;
		} else {
			large[large_count++] = i;
		}
	}
	while (small_count > 0 && large_count > 0) {
		uint32_t low = small[--small_count], high = large[--large_count];
		entries[low].probability = float(scaled[low]);
		entries[low].alias = high;
		scaled[high] = scaled[high] + scaled[low] - 1.0;
		if (scaled[high] < 1.0) {
			small[small_count++] = high;
		} else {
			large[large_count++] = high;
		}
	}
	while (large_count > 0) {
		uint32_t index = large[--large_count];
		entries[index].probability = 1.0f;
		entries[index].alias = index;
	}
	while (small_count > 0) {
		uint32_t index = small[--small_count];
		entries[index].probability = 1.0f;
		entries[index].alias = index;
	}
	// Compute the PDF of the stored FP32 table, rather than the unrounded
	// requested distribution, so the shader compensates its actual proposal.
	double realized[MAX_LIGHTS] = {};
	for (uint32_t i = 0; i < p_count; i++) {
		realized[i] += double(entries[i].probability) / p_count;
		realized[entries[i].alias] += (1.0 - double(entries[i].probability)) / p_count;
	}
	for (uint32_t i = 0; i < p_count; i++) {
		entries[i].source_pdf = float(realized[i]);
		r_entries[i] = entries[i];
	}
	return true;
}

} // namespace RTLightSampling
