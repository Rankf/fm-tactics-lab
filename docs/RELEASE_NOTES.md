# FM 战术实验室 / FM Tactics Lab — v1106

修复顶部一直显示“正在检查本地引擎”的问题。

## 更新内容

- 补齐引擎设置脚本的静态路由，检查状态能够正常刷新。
- 恢复“选择此目录并检查”的事件绑定，支持手动指定游戏路径并查看缺失资源。
- 标题和界面加入 v1106 标识；打包自检新增引擎设置脚本检查。
- 中英文说明和界面截图一并更新到源码包。

下载 `FM27-Tactics-Lab-v1106.exe`，完全退出旧程序（包括托盘），再启动新版。游戏仍需在本机安装，Steam 需登录拥有游戏的账号。EXE 自带 Python，玩家无需安装开发环境。

本版沿用 v1103.2 的原生比赛宿主与比赛逻辑，存档对战功能继续留在后续开发版本中。v1103.2 历史 Release 保留。

## 验证

已验证引擎检查脚本 HTTP 200、版本显示、缺失资源提示、手动切换到正确目录、完整／快速模式各一场真实比赛。两个模式同种子的比分与球队统计一致。完整模式事件校验通过，快速模式正确关闭事件明细。

## English

Fixes the engine status getting stuck on “Checking local engine”.

- Serve the missing engine settings script so status initialization and manual game-path checks work.
- Show actionable missing-resource diagnostics and allow selecting the correct game directory.
- Add v1106 version labels and include the engine script endpoint in packaged startup self-tests.
- Include the bilingual guides and actual UI screenshots in the source package.

Download `FM27-Tactics-Lab-v1106.exe`. Fully exit the old application, including its tray process, before launching the update. FM27 must be installed locally and Steam signed in to the account that owns the game. Python is bundled.

The original v1103.2 native match host is retained. Career-save versus mode remains in later development versions; the historical v1103.2 release stays available.

Validated on the packaged EXE: script HTTP 200, visible version, missing-resource diagnostics, manual path recovery, and one full-mode plus one quick-mode native match with equal same-seed scores and team statistics.

Use `SHA256SUMS.txt` to verify the EXE and `fm-tactics-lab-v1106-source.zip`. Tool code is MIT licensed. See the repository for Chinese and English usage guides and third-party notices.
