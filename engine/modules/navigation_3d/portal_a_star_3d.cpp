/**************************************************************************/
/*  portal_a_star_3d.cpp                                                  */
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

#include "portal_a_star_3d.h"

#include "core/object/class_db.h"

#include <limits>

void PortalAStar3D::_invalidate_costs() {
	costs_dirty = true;
	target_costs.clear();
	heuristic_fields.clear();
}

void PortalAStar3D::set_native_costs_enabled(bool p_enabled) {
	native_costs_enabled = p_enabled;
	_invalidate_costs();
}

void PortalAStar3D::configure_portal_connections(const PackedInt64Array &p_connections, double p_cost) {
	ERR_FAIL_COND_MSG(p_connections.size() % 2 != 0, "Portal connections must contain pairs of point IDs.");
	ERR_FAIL_COND_MSG(!Math::is_finite(p_cost) || p_cost < 0.0, "Portal cost must be finite and nonnegative.");
	HashSet<int64_t> endpoints;
	for (int i = 0; i < p_connections.size(); i += 2) {
		ERR_FAIL_COND_MSG(!has_point(p_connections[i]) || !has_point(p_connections[i + 1]), "Portal endpoints must exist in the graph.");
		endpoints.insert(p_connections[i]);
		endpoints.insert(p_connections[i + 1]);
		ERR_FAIL_COND_MSG(endpoints.size() > 128, "PortalAStar3D supports up to 128 portal endpoints.");
	}
	portal_connections = p_connections;
	portal_cost = p_cost;
	_invalidate_costs();
}

void PortalAStar3D::_rebuild_costs() {
	portal_ids.clear();
	portal_positions.clear();
	portal_edges.clear();
	for (int i = 0; i < portal_connections.size(); i += 2) {
		const int64_t from = portal_connections[i];
		const int64_t to = portal_connections[i + 1];
		// Removing a point also removes its old shortcut from the lower bound.
		if (!has_point(from) || !has_point(to)) {
			continue;
		}
		portal_edges.insert(Pair<int64_t, int64_t>(from, to));
		for (int64_t id : { from, to }) {
			if (!portal_ids.has(id)) {
				portal_ids.push_back(id);
				portal_positions.push_back(get_point_position(id));
			}
		}
	}
	const int count = portal_ids.size();
	portal_metric.resize(count * count);
	double *metric = portal_metric.ptrw();
	for (int i = 0; i < count; i++) {
		for (int j = 0; j < count; j++) {
			metric[i * count + j] = portal_edges.has(Pair<int64_t, int64_t>(portal_ids[i], portal_ids[j])) ? portal_cost : double(portal_positions[i].distance_to(portal_positions[j]));
		}
	}
	// Preserve the legacy Floyd-Warshall order and double-precision sums.
	for (int k = 0; k < count; k++) {
		for (int i = 0; i < count; i++) {
			for (int j = 0; j < count; j++) {
				metric[i * count + j] = MIN(metric[i * count + j], metric[i * count + k] + metric[k * count + j]);
			}
		}
	}
	costs_dirty = false;
}

real_t PortalAStar3D::_compute_cost(int64_t p_from_id, int64_t p_to_id) {
	if (!native_costs_enabled) {
		return AStar3D::_compute_cost(p_from_id, p_to_id);
	}
	if (costs_dirty) {
		_rebuild_costs();
	}
	if (portal_edges.has(Pair<int64_t, int64_t>(p_from_id, p_to_id))) {
		return portal_cost;
	}
	return get_point_position(p_from_id).distance_to(get_point_position(p_to_id));
}

real_t PortalAStar3D::_estimate_cost(int64_t p_from_id, int64_t p_to_id) {
	if (!native_costs_enabled) {
		return AStar3D::_estimate_cost(p_from_id, p_to_id);
	}
	if (costs_dirty) {
		_rebuild_costs();
	}
	const Vector3 source = get_point_position(p_from_id);
	const Vector3 destination = get_point_position(p_to_id);
	const int count = portal_ids.size();
	if (count == 0) {
		return source.distance_to(destination);
	}
	HashMap<int64_t, double> *field = heuristic_fields.getptr(p_to_id);
	if (field) {
		const double *cached = field->getptr(p_from_id);
		if (cached) {
			return *cached;
		}
	} else {
		if (heuristic_fields.size() >= 96) {
			heuristic_fields.erase(heuristic_fields.begin()->key);
		}
		heuristic_fields.insert(p_to_id, HashMap<int64_t, double>());
		field = heuristic_fields.getptr(p_to_id);
	}
	const Vector<double> *tails = target_costs.getptr(p_to_id);
	if (!tails) {
		Vector<double> costs;
		costs.resize(count);
		for (int i = 0; i < count; i++) {
			double best = std::numeric_limits<double>::infinity();
			for (int j = 0; j < count; j++) {
				best = MIN(best, portal_metric[i * count + j] + double(portal_positions[j].distance_to(destination)));
			}
			costs.write[i] = best;
		}
		target_costs.insert(p_to_id, costs);
		tails = target_costs.getptr(p_to_id);
	}
	double best = source.distance_to(destination);
	for (int i = 0; i < count; i++) {
		best = MIN(best, double(source.distance_to(portal_positions[i])) + (*tails)[i]);
	}
	field->insert(p_from_id, best);
	return best;
}

void PortalAStar3D::_point_data_changed(bool p_cleared) {
	if (p_cleared) {
		portal_connections.clear();
	}
	_invalidate_costs();
}

void PortalAStar3D::_bind_methods() {
	ClassDB::bind_method(D_METHOD("configure_portal_connections", "connections", "cost"), &PortalAStar3D::configure_portal_connections, DEFVAL(3.0));
	ClassDB::bind_method(D_METHOD("set_native_costs_enabled", "enabled"), &PortalAStar3D::set_native_costs_enabled);
	ClassDB::bind_method(D_METHOD("is_native_costs_enabled"), &PortalAStar3D::is_native_costs_enabled);
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "native_costs_enabled"), "set_native_costs_enabled", "is_native_costs_enabled");
}
