/**************************************************************************/
/*  portal_a_star_3d.h                                                    */
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

#include "core/math/a_star.h"
#include "core/templates/hash_map.h"
#include "core/templates/hash_set.h"

// Native portal-aware lower bound. The AStar3D search, point
// weights, directed connections and disabled-point handling remain unchanged.
class PortalAStar3D : public AStar3D {
	GDCLASS(PortalAStar3D, AStar3D);

	bool native_costs_enabled = true;
	bool costs_dirty = true;
	double portal_cost = 3.0;
	PackedInt64Array portal_connections;
	HashSet<Pair<int64_t, int64_t>> portal_edges;
	Vector<int64_t> portal_ids;
	Vector<Vector3> portal_positions;
	Vector<double> portal_metric;
	HashMap<int64_t, Vector<double>> target_costs;
	HashMap<int64_t, HashMap<int64_t, double>> heuristic_fields;

	void _invalidate_costs();
	void _rebuild_costs();

protected:
	static void _bind_methods();
	void _point_data_changed(bool p_cleared) override;
	real_t _compute_cost(int64_t p_from_id, int64_t p_to_id) override;
	real_t _estimate_cost(int64_t p_from_id, int64_t p_to_id) override;

public:
	void set_native_costs_enabled(bool p_enabled);
	bool is_native_costs_enabled() const { return native_costs_enabled; }
	void configure_portal_connections(const PackedInt64Array &p_connections, double p_cost = 3.0);
};
