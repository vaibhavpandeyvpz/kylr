# Desktop packages

Use official Godot 4.7.2 and matching export templates on Windows, macOS or Linux. Run
`tools/package.ps1 -Version dev-local -Godot $Godot` from `game/`, as
shown in [the README](../game/README.md#tagged-packages-and-github-releases).

The packager checks native dependencies, notices, PCK payloads and exported
startup. Distribute the complete package, including PCK and native
libraries. Windows/macOS ship ZIPs; Linux ships tar.gz. Windows builds are
unsigned; macOS uses ad-hoc signing without notarization. Reports/build
directories are generated and ignored. Passing
packaging does not establish visual, audio or performance qualification.

The root [release workflow](../.github/workflows/package.yml) installs official
Godot and export templates on all three OSes, checks each native export, runs
the game suite once on Linux and publishes the tagged packages together after every build succeeds. Manual runs
on `main` upload artifacts; manual runs on a `v*` tag publish releases too. See
[build and release](BUILD_AND_RELEASE.md) for prerequisites and CI qualification. Renderer quality gates remain separate from packaging.

For updates, quit the game, verify archive hashes and unpack to a new directory.
Keep the previous package for rollback; do not mix executables, PCKs, extensions
or incompatible peers. Account rollback requires a schema-compatible API or an
inspected database restore. See [ONLINE.md](ONLINE.md) for service maintenance.
