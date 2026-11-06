# v1103.2 provenance and validation

## Release identity

- Original filename: `FM27战术推演_v1103.2.exe`.
- SHA256: `b18594de3fcfecbb520e73c86555e122eb899dbadc2ff3402dd0f839329f1614`.
- Size: 12,319,232 bytes.
- Embedded payload SHA256: `8ec66ee7528d0ad60161207b93fedee2ec5cf97dc73af9314d719c289070fc6d`.
- Native host SHA256: `6a537a8c58736186272ffd16fa895df0084e7ceb2a7659fa829c3ba5b8630f61`.

The original executable is identical to the previously accepted compatibility-startup build. Its Python and UI sources were recovered from that payload. The matching native build snapshot contains 77 compatibility ranges, totalling 69,675 bytes. Public metadata stores addresses, lengths and hashes; original comparison bytes are generated locally.

The source launcher removes the workstation-specific fallback path. Build scripts are newly organized for external contributors. The release EXE is not rebuilt. GitHub download name: `FM27-Tactics-Lab-v1103.2.exe`; its bytes and SHA256 are unchanged.

## Historical packaged acceptance

The maintainer's compatibility-startup acceptance records report 10 packaged full/quick/cancel/resume matches and 4 unverified-trial matches, including matching core results and statistics. These are historical checks of the original binary, not a new game-UI equivalence test.

The original EXE does not contain `game_plugin.dll`, game FMF resource archives, user career saves, browser profiles or the save-versus modules. It contains CPython's runtime DLLs, its license, and the named initial inputs needed by this desktop version.

## Publication checks

Publication checks completed: all 23 Python/UI source files match the original payload; Python and JavaScript syntax checks passed; all four source-boundary and profile tests passed; verified-EXE input extraction passed; the public native sources compiled successfully with MSVC x64; regenerated compatibility metadata exactly matches the accepted snapshot; the original EXE startup self-test returned exit code 0 and `ok=true`. The startup self-test does not execute a complete match.
