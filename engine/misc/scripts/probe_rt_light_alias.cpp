// SPDX-License-Identifier: MIT
// Standalone numerical fixture for the renderer's actual alias-table builder.
// JSON output is checked independently by verify_rt_light_alias.py.
#include "servers/rendering/renderer_rd/forward_clustered/rt_light_sampling.h"

#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

static void emit_case(const char *p_name, uint32_t p_count, const double *p_weights, bool p_finite = true) {
	RTLightSampling::AliasEntry entries[RTLightSampling::MAX_LIGHTS + 1];
	for (auto &entry : entries) {
		entry.source_pdf = -7.0f;
		entry.probability = -7.0f;
		entry.alias = 12345;
	}
	bool accepted = RTLightSampling::build_alias_table(p_weights, p_count, entries);
	bool untouched = true;
	for (const auto &entry : entries) {
		untouched = untouched && entry.source_pdf == -7.0f && entry.probability == -7.0f && entry.alias == 12345;
	}
	std::cout << "{\"name\":\"" << p_name << "\",\"count\":" << p_count << ",\"accepted\":" << (accepted ? "true" : "false")
			  << ",\"output_untouched\":" << (untouched ? "true" : "false") << ",\"weights\":[";
	if (p_finite && p_weights) {
		for (uint32_t i = 0; i < p_count; i++) {
			if (i) std::cout << ',';
			std::cout << p_weights[i];
		}
	}
	std::cout << "],\"entries\":[";
	if (accepted) {
		for (uint32_t i = 0; i < p_count; i++) {
			if (i) std::cout << ',';
			std::cout << '[' << entries[i].source_pdf << ',' << entries[i].probability << ',' << entries[i].alias << ']';
		}
	}
	std::cout << "]}\n";
}

int main() {
	std::cout << std::setprecision(17);
	double weights[RTLightSampling::MAX_LIGHTS + 1] = {};
	emit_case("one-zero", 1, weights);
	emit_case("all-zero", 64, weights);
	for (double &weight : weights) weight = 1.0;
	emit_case("uniform", 64, weights);
	weights[0] = 1e30;
	emit_case("dominant", 64, weights);
	for (uint32_t i = 0; i < 64; i++) weights[i] = i % 3 == 0 ? 0.0 : double(i + 1);
	emit_case("mixed-zero", 64, weights);
	for (uint32_t i = 0; i < 64; i++) weights[i] = std::pow(3.0, double(i) - 32.0);
	emit_case("wide", 64, weights);
	for (uint32_t i = 0; i < 64; i++) weights[i] = 1e308;
	emit_case("large", 64, weights);
	for (uint32_t i = 0; i < 64; i++) weights[i] = std::numeric_limits<double>::denorm_min();
	emit_case("subnormal", 64, weights);
	for (uint32_t i = 0; i < 17; i++) weights[i] = i == 0 ? 25.0 : 0.15;
	emit_case("unequal-17", 17, weights);
	emit_case("count-zero", 0, weights);
	emit_case("count-large", 65, weights);
	weights[0] = -1.0;
	emit_case("negative", 17, weights);
	weights[0] = std::numeric_limits<double>::infinity();
	emit_case("infinite", 17, weights, false);
	weights[0] = std::numeric_limits<double>::quiet_NaN();
	emit_case("nan", 17, weights, false);
	emit_case("null-input", 17, nullptr);
	return 0;
}
