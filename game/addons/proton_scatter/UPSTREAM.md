# ProtonScatter

Source: https://github.com/HungryProton/scatter
Version: 4.2.0
Commit: 7198cc00078ebde61307578137c3f35223c6e438
License: MIT; retain LICENSE and LICENSE.md in distribution.

The addon sources, editor tools, shapes, presets and modifiers are vendored
unchanged. Upstream demo assets and tests are omitted. Import settings retain upstream resource UIDs.

`game/scripts/world/energy_core_scatter.gd` consumes the native Add Single Item,
Create Inside (Random) and Project On Colliders modifiers through a modifier
stack. Its physics helper executes the projection batch synchronously during
the authoritative drop transaction. The game filters the resulting positions
for core-footprint support, solid clearance, same-floor height and 25-35 cm
neighbor spacing. Each pickup remains an ordinary, independently moving Core
owned and replicated by the match; it is not a MultiMesh instance.

Runtime placement does not require the editor plugin to be enabled. To use the
visual modifier editor, enable ProtonScatter in Project Settings > Plugins after
the initial asset import has completed.
