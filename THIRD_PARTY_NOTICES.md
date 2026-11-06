# Third-party notices and asset scope

The tool code in this repository is distributed under the MIT license. This is an independent project; game names identify the supported product.

## Public source

The source package contains the Python application, browser UI, C# launcher, C++ adapter, scripts and interface metadata. It excludes original game binaries, machine-code comparison tables, initial PKM inputs and input snapshots.

## Desktop release

The original v1103.2 EXE is a separate desktop distribution. It includes a private CPython 3.12 runtime and its `LICENSE.txt`, the tool's native host, compatibility comparison data and matching initial inputs. It loads the original engine DLL and game resource archives from the user's installation; those game components are not included in the EXE.

The MIT grant covers the tool code. It does not relicense game-related inputs, extracted comparison bytes, third-party components or their trademarks. CPython and its bundled components retain the licenses shipped in the runtime. Windows SDK, MSVC and .NET Framework are build prerequisites and are not included in the source archive.

This v1103.2 source release has no fmsave or backports-zstd dependency. Career-save versus work remains in later development versions.
