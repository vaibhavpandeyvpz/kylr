#!/usr/bin/env python3
"""Independent numerical feasibility test for a cone/GGX sampling mixture.

No renderer setting or shader is changed by this test. It integrates several
nonconstant functions by independent cone quadrature, and compares uniform and
visible-normal reflection sampling with the complete mixture PDF. Rejections
outside the emitter remain zero samples; they must never be resampled away.
Reference: https://jcgt.org/published/0007/04/01/ (Heitz, 2018).
The numerical GGX routine follows the existing brdf_inc.glsl implementation,
whose original BRDF sample is CC0, by Jakub Boksansky (February 2021).
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


def basis(axis):
    tangent = unit(np.cross(axis, [0, 1, 0]))
    return tangent, np.cross(axis, tangent)


def cone_sample(u, axis, cosine):
    z = 1 - u[:, 0] * (1 - cosine)
    radius = np.sqrt(np.maximum(0, 1 - z * z))
    phi = 2 * np.pi * u[:, 1]
    x, y = basis(axis)
    return z[:, None] * axis + radius[:, None] * (
        np.cos(phi)[:, None] * x + np.sin(phi)[:, None] * y)


def ggx_sample(u, view, alpha):
    vh = unit(view * [alpha, alpha, 1])
    lensq = vh[0] ** 2 + vh[1] ** 2
    t1 = np.array([-vh[1], vh[0], 0]) / np.sqrt(lensq) if lensq else np.array([1., 0, 0])
    t2 = np.cross(vh, t1)
    radius = np.sqrt(u[:, 0])
    a = radius * np.cos(2 * np.pi * u[:, 1])
    b = radius * np.sin(2 * np.pi * u[:, 1])
    s = (1 + vh[2]) / 2
    b = (1 - s) * np.sqrt(np.maximum(0, 1 - a * a)) + s * b
    nh = a[:, None] * t1 + b[:, None] * t2 + np.sqrt(
        np.maximum(0, 1 - a * a - b * b))[:, None] * vh
    h = unit(nh * [alpha, alpha, 1])
    return 2 * (h @ view)[:, None] * h - view


def distribution(z, alpha):
    a2 = alpha * alpha
    return a2 / (np.pi * (z * z * (a2 - 1) + 1) ** 2)


def masking(z, alpha):
    return 2 * z / np.maximum(z + np.sqrt(alpha * alpha + (1 - alpha * alpha) * z * z), 1e-30)


def reflection_pdf(direction, view, alpha):
    h = unit(direction + view)
    return np.where((h[:, 2] > 0) & ((h @ view) > 0),
                    distribution(h[:, 2], alpha) * masking(view[2], alpha) / (4 * view[2]), 0)


def integrand(direction, view, alpha):
    """Independent diffuse, microfacet and smooth non-BRDF test functions."""
    nl = np.maximum(direction[:, 2], 0)
    h = unit(direction + view)
    microfacet = distribution(np.maximum(h[:, 2], 0), alpha) * masking(view[2], alpha) * masking(nl, alpha) / (4 * view[2])
    fresnel = .8 + .2 * (1 - np.maximum(h @ view, 0)) ** 5
    return np.stack((nl / np.pi, microfacet * fresnel,
                     nl * (.2 + direction[:, 0] ** 2 + .3 * direction[:, 1])), axis=-1)


def quadrature(axis, cosine, view, alpha, order):
    # Integrate in cone solid angle (uniform z/azimuth), not the GGX mapping.
    roots, weights = np.polynomial.legendre.leggauss(order)
    azimuths = 2 * order
    u0 = np.repeat((roots + 1) / 2, azimuths)
    u1 = np.tile((np.arange(azimuths) + .5) / azimuths, order)
    values = integrand(cone_sample(np.stack((u0, u1), axis=-1), axis, cosine), view, alpha)
    return np.sum(values.reshape(order, azimuths, 3).mean(axis=1) * weights[:, None] / 2, axis=0)


def run(samples):
    rng = np.random.default_rng(593)
    cases = []
    for angle, roughness, cone_angle, offset in (
        (.0, .15, .5, .0), (.65, .15, .5, .0), (1.2, .2, .35, .0),
        (.65, .35, .5, .12), (.65, .6, .5, -.15), (.65, .35, .04, .0),
        (.65, .2, .12, .15), (1.2, .35, .5, -.4),
    ):
        view = np.array([np.sin(angle), 0, np.cos(angle)])
        axis = np.array([-np.sin(angle + offset), 0, np.cos(angle + offset)])
        cosine, alpha = np.cos(cone_angle), roughness ** 2
        reference = quadrature(axis, cosine, view, alpha, 256)
        refined = quadrature(axis, cosine, view, alpha, 384)
        convergence = np.abs(reference - refined) / np.maximum(np.abs(refined), 1e-10)
        estimates = {}
        # A deliberately limited feasibility policy. Broad rough lobes and
        # tiny emitters already favor uniform light sampling; unconditional
        # mixing can waste most of the GGX draws outside the emitter.
        gated_fraction = .5 if cone_angle > 4 * alpha else 0.
        for mode in ('uniform', 'mixture', 'gated_mixture'):
            fraction = .5 if mode == 'mixture' else gated_fraction if mode == 'gated_mixture' else 0.
            u = rng.random((samples, 2))
            direction = cone_sample(u, axis, cosine)
            if fraction:
                choice = rng.random(samples) < fraction
                direction[choice] = ggx_sample(u[choice], view, alpha)
            cone_pdf = np.where(direction @ axis >= cosine - 1e-12, 1 / (2 * np.pi * (1 - cosine)), 0)
            density = (1 - fraction) * cone_pdf + fraction * reflection_pdf(direction, view, alpha)
            weight = np.divide(cone_pdf, density, out=np.zeros_like(density), where=density > 0)
            values = integrand(direction, view, alpha) * weight[:, None]
            mean = values.mean(axis=0)
            variance = values.var(axis=0, ddof=1)
            error = np.abs(mean - refined)
            allowed = 6 * np.sqrt(variance / samples) + .004 * np.abs(refined) + 1e-6
            mass = float(weight.mean())
            mass_allowed = 6 * float(weight.std(ddof=1)) / np.sqrt(samples) + .001
            estimates[mode] = dict(ggx_fraction=fraction, mean=mean.tolist(), variance=variance.tolist(),
                                   relative_error=(error / np.maximum(np.abs(refined), 1e-10)).tolist(),
                                   constant_integrand_mean=mass,
                                   energy_pass=bool(np.all(error <= allowed) and abs(mass - 1) <= mass_allowed))
        cases.append(dict(view_angle=angle, roughness=roughness, cone_angle=cone_angle,
                          cone_offset=offset, quadrature=refined.tolist(),
                          quadrature_relative_change=convergence.tolist(), estimates=estimates,
                          specular_variance_ratio=estimates['mixture']['variance'][1] / estimates['uniform']['variance'][1],
                          gated_specular_variance_ratio=estimates['gated_mixture']['variance'][1] / estimates['uniform']['variance'][1],
                          passed=bool(np.all(convergence < .004) and all(e['energy_pass'] for e in estimates.values()))))
    # Omitting the proposal density is a substantive energy error, not another
    # legal sampling policy. This deterministic negative must remain detectable.
    negative = np.array(cases[0]['estimates']['mixture']['mean']) * .5
    negative_rejected = bool(np.any(np.abs(negative - cases[0]['quadrature']) > .1 * np.array(cases[0]['quadrature'])))
    return dict(passed=all(c['passed'] for c in cases) and negative_rejected,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                samples_per_case=samples, cases=cases, wrong_pdf_negative_rejected=negative_rejected,
                renderer_changed=False, gpu_validated=False, production_qualified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=400000)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output; preserve earlier evidence.')
    if args.samples < 10000:
        parser.error('At least 10000 independent samples are required.')
    result = run(args.samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=result['passed'], cases=len(result['cases']),
                         specular_variance_ratios=[c['specular_variance_ratio'] for c in result['cases']],
                         gated_specular_variance_ratios=[c['gated_specular_variance_ratio'] for c in result['cases']])))
    raise SystemExit(0 if result['passed'] else 1)
