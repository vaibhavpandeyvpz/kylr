/**************************************************************************/
/*  test_frame_token.cpp                                                  */
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

#include "../streamline_frame_token.h"

#include <atomic>
#include <cassert>
#include <iostream>
#include <thread>

int main() {
	int first = 1, second = 2, next = 3;
	assert(!StreamlineRenderFrameScope::is_active());
	{
		StreamlineRenderFrameScope outer(&first);
		assert(StreamlineRenderFrameScope::get_token() == &first);
		{
			StreamlineRenderFrameScope nested(&second);
			assert(StreamlineRenderFrameScope::get_token() == &second);
		}
		assert(StreamlineRenderFrameScope::get_token() == &first);
		{
			StreamlineRenderFrameScope empty(nullptr);
			assert(StreamlineRenderFrameScope::is_active());
			assert(StreamlineRenderFrameScope::get_token() == nullptr);
		}
		assert(StreamlineRenderFrameScope::get_token() == &first);
	}
	assert(!StreamlineRenderFrameScope::is_active());
	std::atomic<void *> latest(&first);
	std::atomic<int> phase(0);
	std::thread renderer([&]() {
		StreamlineRenderFrameScope draw(latest.load());
		phase.store(1);
		while (phase.load() != 2) {
			std::this_thread::yield();
		}
		assert(latest.load() == &next);
		assert(StreamlineRenderFrameScope::get_token() == &first);
	});
	while (phase.load() != 1) {
		std::this_thread::yield();
	}
	latest.store(&next);
	assert(!StreamlineRenderFrameScope::is_active());
	phase.store(2);
	renderer.join();
	assert(!StreamlineRenderFrameScope::is_active());
	std::cout << "FRAME_TOKEN_SCOPE_PASS\n";
}
