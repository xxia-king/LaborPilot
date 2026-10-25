# WorkBuddy 专家适配

本适配使用同一 GitHub 仓库的长期 `workbuddy` 分支，当前基于公开版 `v1.4.4`（`c2a86ff`），版本保持 `1.4.4`。`main` 保存供 GitHub 下载和 Agent 安装的普通插件；`workbuddy` 保存经 WorkBuddy 专家渠道上传的专用交付包。专家清单、提示词和头像仅在本分支维护，不合入 `main`。

## 源码与安装目录

Git 仓库是修改入口；WorkBuddy 的 `~/.workbuddy/plugins/marketplaces/my-experts/plugins/laborpilot/` 是安装副本，备份和核对后才更新。不要直接在安装目录开发，也不要将安装副本整包覆盖回源码仓库。

仅有以下三项平台适配资源，另外维护变更说明与本文：

- `.codebuddy-plugin/plugin.json`：专家清单，直接引用根目录下的 10 个 `skills/`。
- `agents/laborpilot.md`：专家提示词，无 `tools` 字段。
- `avatars/laborpilot.png`：专家头像。

`skills/`、`scripts/`、`references/`、`workflow/`、`data/`、`assets/` 共用上游实现。根目录 `SKILL.md` 必须保留，专家提示词会读取它。不得复制可编辑卡库或法规语料到本仓。

专家标识统一为 `laborpilot`：清单 `name`、`agentName`、打包根目录名和 `agents/laborpilot.md` 文件名一致。GitHub 仓库名仍可为 `LaborPilot`，但本地校验与打包目录应使用小写 `laborpilot`。

## 校验与打包

需要 Python 3.11+；文书测试需要 Pandoc。`EXPERT_MANAGER` 指向本机当前有效的 WorkBuddy `skill-expert-manager` 目录，更新 WorkBuddy 后应重新确认路径。

在源码仓库运行：

```bash
python3 scripts/sync_version.py --check
python3 -m unittest discover -s tests -v
```

提交完成后，必须从指定 Git 提交导出到临时目录再打包。`git archive` 会按 `.gitattributes` 自动排除维护记录，同时避免混入未跟踪的案件资料、本地配置或其他开发产物；不要直接将工作目录交给打包器：

```bash
stage_dir=$(mktemp -d)
expert_dir="$stage_dir/plugins/marketplaces/my-experts/plugins/laborpilot"
mkdir -p "$expert_dir"
git archive HEAD | tar -x -C "$expert_dir"
# 维护记录不得进入专家包；任一检查失败立即停止。
test ! -e "$expert_dir/TASKS.md" || exit 1
test ! -e "$expert_dir/AILOG.md" || exit 1
test ! -e "$expert_dir/docs/maintenance" || exit 1
WORKBUDDY_CONFIG_DIR="$stage_dir" python3 "$EXPERT_MANAGER/scripts/validate_expert.py" "$expert_dir"
WORKBUDDY_CONFIG_DIR="$stage_dir" python3 "$EXPERT_MANAGER/scripts/package_expert.py" "$expert_dir" "$stage_dir/dist"
```

新版官方校验器要求专家位于配置目录内；以上命令用它支持的 `WORKBUDDY_CONFIG_DIR` 建立临时配置目录，不改动真实安装。

临时产物为 `$stage_dir/dist/laborpilot.zip`。校验完成后，将 ZIP 放到本机 `plugins办案引擎/` 目录，命名为 `LaborPilot-v<版本>-WorkBuddy专家包.zip`，例如 `LaborPilot-v1.4.4-WorkBuddy专家包.zip`。历史 ZIP 统一归入该目录的 `_archive/`；专家源码目录内不长期存放 ZIP。ZIP 内的根目录仍保持 `laborpilot/`。官方校验通过只证明包结构符合要求；安装后仍需在 WorkBuddy 中验证专家加载、Skill 路由和真实任务。更新安装目录前先备份，再通过 WorkBuddy 的导入流程安装。

## 后续更新

先确认 `origin/main` 的变化以及其他本地开发分支的未发布工作，再决定本分支基线。不得把其他分支的开发成果或版本号混入本次 1.4.4 适配。平台通用的引擎修复在主线统一维护；更新专家版时，将所需主线更新同步到 `workbuddy`，检查冲突、重新校验和打包，再经 WorkBuddy 专家渠道上传。不得将专家包装文件反向合入普通插件，也不要在安装副本内开发。

未来升级版本时，现有 `scripts/sync_version.py` 是否覆盖 WorkBuddy 清单需要另行核验，并确保 `VERSION` 与 `.codebuddy-plugin/plugin.json` 的 `version` 一致。

## 维护记录同步

根级 `TASKS.md`、`AILOG.md` 与 `docs/maintenance/` 随 `workbuddy` 分支同步，供维护者通过 Git clone 接续；`.gitattributes` 将它们排除在 `git archive` 和 GitHub 源码 ZIP 外。任务状态只在源码仓的 `TASKS.md` 维护。原始备份、本机详细日志和清理清单继续保存在源码仓之外。
