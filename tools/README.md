# Workspace build tools

Run these scripts from the repository root with PowerShell 7:

- `prepare_godot.py`: download checksum-pinned official Godot 4.7.2 and optional
  matching export templates into ignored local directories.
- `godot-release.json`: official release archive checksums used by Windows and Linux builds.
- `install_animations.py`: validate Mixamo downloads and install local retarget output.
- `download_epidemic_audio.py`: authenticated MCP sound-effect downloads to ignored cache.
- `install_epidemic_audio.py`: restore exact library/game PCM cues from pinned licensed sources.
- `requirements-audio.txt`: Python 3.12 PCM preparation dependency.
- `install_private_assets.py`: verify and restore a private ZIP downloaded by the AWS CLI or validate local assets.
- `requirements-assets.txt`: original texture-generation dependencies.
- `install_customisation_thumbnails.py`: compress authored Blender head, emote and torso portraits into 192 px WebP tiles (requires Pillow).
- `install_upper_body_showcase.py`: compose the README gallery from six 1024 px Blender upper-body portraits (requires Pillow).
- `configure_online.py`: set the public HTTPS account-service origin in a client build.
- `publish_edgegap_version.py`: register a private immutable server image after CI publication.

Follow [licensed asset setup](../docs/ASSET_SETUP.md) before the first game import.
Run focused installer checks with
`python -m unittest discover -s tools/tests -v` after installing the asset/audio
requirements. Credentialed downloads require a separately licensed account.

[Game tools](../game/tools/README.md) own import, testing, benchmarking and packaging.
[Build and release](../docs/BUILD_AND_RELEASE.md) describes the complete pipeline.
[Cloud hosting](../docs/CLOUD_HOSTING.md) lists Render/Atlas settings and Edgegap publication variables.
