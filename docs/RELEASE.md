# Windows packages

Build the matching custom editor and `template_release` in the sibling engine.
Use `tools/package_windows.ps1 -Version dev-local -Godot $Godot` as described in
[the README](../game/README.md#tagged-packages-and-github-releases). Stock Godot
export templates do not contain this renderer.

The packager verifies runtime signatures/hashes, notices, PCK payloads and
exported startup. Distribute the whole unsigned package, including PCK and
native libraries. Reports/build directories are generated and ignored. Passing
packaging does not establish visual, audio or performance qualification.

The root [release workflow](../.github/workflows/package.yml) now builds the custom
engine before the game and publishes verified tagged packages. See
[build and release](BUILD_AND_RELEASE.md) for prerequisites and CI qualification.
Renderer quality gates remain separate from packaging.

For updates, quit the game, verify archive hashes and unpack to a new directory.
Keep the previous package for rollback; do not mix executables, PCKs, extensions
or incompatible peers. Account rollback requires a schema-compatible API or an
inspected database restore. See [ONLINE.md](ONLINE.md) for service maintenance.
