# Workspace build tools

Run these scripts from the repository root with PowerShell 7:

- `prepare_windows_dependencies.ps1`: stage and verify pinned production
  Streamline runtimes/notices and Microsoft C++ runtime files.
- `engine/misc/scripts/build_windows.ps1`: build the custom editor or export
  template with installed Visual Studio C++ tools and SCons.
- `requirements-build.txt`: pinned build-tool dependency.
- `install_animations.py`: validate Mixamo downloads and install local retarget output.
- `download_epidemic_audio.py`: authenticated MCP sound-effect downloads to ignored cache.
- `install_epidemic_audio.py`: restore exact library/game PCM cues from pinned licensed sources.
- `requirements-audio.txt`: Python 3.12 PCM preparation dependency.
- `install_private_assets.py`: verify and restore a private ZIP downloaded by the AWS CLI or validate local assets.
- `requirements-assets.txt`: original texture-generation dependencies.

Follow [licensed asset setup](../docs/ASSET_SETUP.md) before the first game import.
Run focused installer checks with
`python -m unittest discover -s tools/tests -v` after installing the asset/audio
requirements. Credentialed downloads require a separately licensed account.

[Game tools](../game/tools/README.md) own import, testing, benchmarking and packaging.
[Build and release](../docs/BUILD_AND_RELEASE.md) describes the complete pipeline.
