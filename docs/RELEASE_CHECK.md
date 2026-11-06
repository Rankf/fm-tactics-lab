# v1106 packaged update validation

- EXE: `FM27-Tactics-Lab-v1106.exe`.
- EXE SHA256: `e05f81c8100e626bbff838e04e4c8cb9b962e5158a7c6c3c918cde06f95cec22`.
- Embedded payload SHA256: `d184d2a0d0b5866ad35e473996536a88cec86c1355754687d1f394165ecec26d`.
- Native host SHA256: `6a537a8c58736186272ffd16fa895df0084e7ceb2a7659fa829c3ba5b8630f61` (identical to the original v1103.2 host).
- Actual packaged browser: title and version badge show v1106; `engine-settings.js` returns HTTP 200; engine status changes from missing resources to verified after manual game-directory selection; no browser console errors.
- Two actual packaged native matches, seed 42: full and quick modes each complete with score 0:3 and identical team statistics, zero failures. Full-mode incident registry verification succeeds; quick-mode events are disabled as intended.
- Python/JavaScript syntax checks and all four release-boundary/profile tests pass. Input preparation from the verified v1106 EXE succeeds.
- Missing-game startup self-test also passes with the engine script endpoint included in the launcher self-test.

The v1103.2 tag and download assets remain unchanged. The following records describe that historical release.

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
