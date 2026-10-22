# Industrial chrome reflection map

`industrial_chrome.png` is an original AI-generated square grayscale reflection
map created for this project from the user's industrial chrome reference.
The supplied reference is not bundled or sampled by the game.

The shared sky material samples this texture with spherical UV coordinates only
in its radiance-cubemap pass. Godot prefilters that cubemap for material roughness.
All environment-reflecting materials use it, including steel, bronze, copper,
aluminium, titanium and the original thin-dielectric glass across asset categories.
It is not an albedo texture and does not replace the visible cosmic sky.
A low neutral floor keeps dark reflections legible; edge fades suppress joins.
The panorama supplies the authored metallic reflection fill.

Runtime finishes are shared through `Assets.finish_metals`. Coverage uses authored
metallic values as well as named bright alloys, so weapon frames, robot armour,
copper, bronze and other imported hardware receive the same environment. Coloured
paint retains its authored colour and metallic fraction with a subtle satin coat.
Authored roughness textures remain active; their factor is reduced by only 10%.
Dark matte chassis and grips retain their rough finish and still receive the
roughness-filtered environment. Glass retains its separate original shader.

Run `tools/audit_metal_materials.gd` headlessly to inventory imported material
coverage, and `tools/preview_reflection_materials.gd` with rendering enabled to
inspect representative metal, paint and glass finishes in arena lighting.

Generation prompt: original square black environment with futuristic geometric
chambers, curved dark metal panels, white rectangular lights, silver specular
gradients, no text, branding, watermark or border.
