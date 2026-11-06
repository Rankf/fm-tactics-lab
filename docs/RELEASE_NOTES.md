# FM 战术实验室 / FM Tactics Lab — v1103.2

首个公开发布版本，使用原版 FM27 详细比赛引擎，在本机批量测试战术。

## 下载与使用

下载 `FM27战术推演_v1103.2.exe`，打开 Steam 并登录拥有游戏的账号，双击运行。EXE 自带 Python，玩家无需安装开发环境。首次启动后确认游戏目录，导入 FMF 战术，设置双方球员，选择场数并运行。

本次提供指定的 v1103.2 原始 EXE。包含双阶段战术、球员编辑、定位球、同种子战术对比、比分与原版统计、完整／快速采集模式，以及兼容性分级和手动选择游戏路径。存档对战功能暂留在后续开发版本中。

源码包：`fm-tactics-lab-v1103.2-source.zip`。中英文使用说明位于仓库 README。Windows x64；适配参考构建 `27.0.0+2493426`。快速模式仍计算详细整场比赛，只减少球员事件明细采集。

## English

The first public release of FM Tactics Lab: batch tactical experiments using the original FM27 detailed match engine.

Download `FM27战术推演_v1103.2.exe`, open Steam and sign in to the account that owns the game, then launch the EXE. Python is included. Select the game directory, import a tactic, configure both squads and run a batch. The desktop UI is in Chinese; English usage instructions are in `README.en.md`.

This release preserves the original v1103.2 executable. It includes possession-phase tactics, player editing, set pieces, paired-seed comparisons, native scores and team statistics, full/quick event collection, and graded engine compatibility. Career-save versus mode remains in later development versions.

Source asset: `fm-tactics-lab-v1103.2-source.zip`. Windows x64; adapter reference build `27.0.0+2493426`. Quick mode still runs detailed full matches, with reduced player-event collection.

Verify downloads using `SHA256SUMS.txt`. Tool source is MIT licensed; third-party and game-related assets retain their own scope as described in `THIRD_PARTY_NOTICES.md`.
