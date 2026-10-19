"""Read-only audit of native model handoff and the shared lunar texture set.

Run with library/.venv/Scripts/python.exe. This does not replace Blender round
trips, rendered previews, collision checks or Godot import/visual verification.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

from handoff_lunar_materials import ROLES, geometry, read, role, texture_infos

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = {
    "baseColorTexture": "regolith_albedo.png",
    "normalTexture": "regolith_normal.png",
    "metallicRoughnessTexture": "regolith_orm.png",
    "occlusionTexture": "regolith_orm.png",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(game):
    errors, rows = [], []
    canonical = game / "assets/textures/lunar_surface"
    texture_rows = []
    for name in sorted(set(CHANNELS.values())):
        source, target = ROOT / "textures/lunar_surface" / name, canonical / name
        valid = source.is_file() and target.is_file() and sha256(source) == sha256(target)
        texture_rows.append({"file": name, "matches_source": valid})
        if not valid:
            errors.append(f"Canonical texture differs or is missing: {name}")
    for path in sorted((game / "assets/models").rglob("*.glb")):
        relative = path.relative_to(game / "assets/models")
        source = ROOT / "models" / relative
        label = path.relative_to(game).as_posix()
        if not source.is_file():
            errors.append(f"Native source export missing: {label}")
            continue
        native, native_binary = read(source)
        document, binary = read(path)
        native_geometry, runtime_geometry = geometry(native, native_binary), geometry(document, binary)
        if native_geometry != runtime_geometry:
            errors.append(f"Geometry, rig, placement, UV or animation differs: {label}")
        textures = document.get("textures", [])
        images = document.get("images", [])
        used_textures = {info["index"] for info in texture_infos(document.get("materials", []))}
        if used_textures != set(range(len(textures))):
            errors.append(f"Unused or invalid texture slots: {label}")
        if {texture.get("source") for texture in textures} != set(range(len(images))):
            errors.append(f"Unused images or unsupported image bindings: {label}")
        if {texture["sampler"] for texture in textures if "sampler" in texture} != set(range(len(document.get("samplers", [])))):
            errors.append(f"Unused or invalid texture samplers: {label}")
        for image in images:
            uri = image.get("uri", "")
            if not uri or uri.startswith("data:"):
                continue
            target = (path.parent / unquote(uri)).resolve()
            if not target.is_relative_to(game) or not target.is_file():
                errors.append(f"Missing or out-of-project texture: {label}: {uri}")
        used_materials = {primitive["material"] for mesh in document.get("meshes", [])
                          for primitive in mesh.get("primitives", []) if "material" in primitive}
        lunar_count = 0
        for index in sorted(used_materials):
            material = document["materials"][index]
            material_role = role(material.get("name", ""))
            if material_role not in ROLES:
                if relative.parts[0] in {"architecture", "weapons"} and list(texture_infos(material)):
                    errors.append(f"Unexpected finish image: {label}: {material.get('name')}")
                continue
            lunar_count += 1
            slots = dict(material.get("pbrMetallicRoughness", {}))
            slots.update(material)
            for channel, filename in CHANNELS.items():
                info = slots.get(channel)
                if not info or not isinstance(info.get("index"), int) or not 0 <= info["index"] < len(textures):
                    errors.append(f"Missing lunar {channel}: {label}: {material_role}")
                    continue
                texture = textures[info["index"]]
                image_index = texture.get("source", -1)
                image = images[image_index] if isinstance(image_index, int) and 0 <= image_index < len(images) else {}
                uri = image.get("uri", "")
                if not uri or (path.parent / unquote(uri)).resolve() != canonical / filename:
                    errors.append(f"Lunar {channel} does not share canonical {filename}: {label}")
        rows.append({"path": label, "source_sha256": sha256(source), "game_sha256": sha256(path),
                     "geometry_sha256": runtime_geometry, "geometry_matches": native_geometry == runtime_geometry,
                     "lunar_materials": lunar_count})
    if not rows:
        errors.append("No model exports were audited")
    preserved = ROOT / "models/environments/cryo_pod/model.py"
    if not preserved.is_file():
        # Discovery is explicit: do not silently accept deletion of the reserved asset.
        candidates = list((ROOT / "models").glob("*/cryo_pod/model.py"))
        if len(candidates) != 1:
            errors.append("Reserved cryo_pod source is missing or ambiguous")
    return {"passed": not errors, "read_only": True, "visual_quality_accepted": False,
            "blender_roundtrip_accepted": False, "godot_import_accepted": False,
            "models": rows, "canonical_textures": texture_rows, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=ROOT.parent / "game")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Use a fresh report path; preserve earlier evidence")
    result = audit(args.game.resolve())
    result["auditor_sha256"] = sha256(Path(__file__))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"passed": result["passed"], "models": len(result["models"]),
                      "errors": result["errors"], "report": str(args.report)}))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
