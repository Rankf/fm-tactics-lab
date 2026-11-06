# Building FM Tactics Lab v1106

The v1106 source follows the v1103.2 desktop payload with the engine-settings static route fix and updated version labels. Career-save versus modules and their dependencies are excluded from this release.

## Requirements

- Windows x64, full CPython 3.12 x64, and MSVC C++17 with the Windows SDK.
- A local FM27 installation; the adapter reference build is `27.0.0+2493426`.
- A verified v1106 or v1103.2 EXE from this repository's Releases, used to supply the matching initial inputs.

The Python application uses the standard library. No save-parser package is needed.

## Prepare local inputs

Run these commands from the repository root:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe scripts/prepare_private.py --release-exe "D:\Downloads\FM27-Tactics-Lab-v1106.exe"
```

The script checks the original EXE and embedded payload SHA256, then reads only the named input assets into ignored `private/` directories. It does not execute the EXE. An existing matching asset directory can alternatively be supplied with `--assets-root` and `--catalog`.

## Build the native adapter

In an **x64 Native Tools Command Prompt for Visual Studio**:

```bat
.venv\Scripts\python.exe scripts\build_native.py --reference-dll "D:\Games\Football Manager 27\fm_Data\Plugins\x86_64\game_plugin.dll"
```

The public repository contains range metadata and digests. The script reconstructs comparison bytes from the exact reference DLL on your machine, verifies every range, then compiles the checked-in C++ host. Generated function bytes remain in ignored local outputs.

## Run from source

```powershell
.venv\Scripts\python.exe scripts/run.py --game-root "D:\Games\Football Manager 27"
```

Open the printed loopback URL after startup. Press `Ctrl+C` to stop the source edition.

## Build a local desktop EXE

```powershell
.venv\Scripts\python.exe scripts/build_exe.py --python-home "D:\Python312"
```

Supply a full CPython 3.12 x64 distribution containing `Lib`, `DLLs`, `python312.dll`, the runtime libraries and `LICENSE.txt`. The script uses the .NET Framework C# compiler; `--csc` can override its location. Output: `dist/FM27-Tactics-Lab-v1106.exe`.

The historical v1103.2 EXE is preserved unchanged. The v1106 desktop release uses the same original native host binary. A local rebuild uses the published source and build scripts; reproducible byte-for-byte executable output is not claimed.

## Validate and export source

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe scripts/export_source.py
```

The exporter uses an explicit source allowlist, checks for workstation paths and common credential formats, and writes file digests inside the archive. It excludes game DLLs, runtime data, input snapshots and generated comparison bytes.

The EXE release is a separate asset authorized for distribution by the maintainer. Its embedded initial inputs and comparison data are outside the MIT grant for tool code. See [third-party notices](../THIRD_PARTY_NOTICES.md).
