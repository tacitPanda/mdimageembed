Building the mdimageembed EXE and installer (Windows)

Prereqs:
- Python 3.8+
- Inno Setup (for building the installer) if you want an installer

Quick build steps (from repo root):
1. Open PowerShell and change to the build folder:
   cd build
2. Run the build script (creates venv, installs deps, generates icon, builds EXE, creates desktop shortcut):
   .\build_exe.ps1

Artifacts:
- release\mdimageembed.exe  (single-file exe)
- release\app.ico
- installer\mdimageembed_setup.exe (if you run Inno Setup with installer\mdimageembed.iss)

Notes:
- To create the installer: open installer\mdimageembed.iss in Inno Setup and build.
- To change the icon text, edit tools\generate_icon.py.
- Code-signing is recommended for distribution to reduce SmartScreen warnings.
