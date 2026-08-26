# LaborPilot 1.3.0 发布收尾记录

- 日期：2026-08-27
- Run ID：`2026-08-27-laborpilot-1.3.0-neat-freak`
- Agent：Codex
- 范围：LaborPilot 1.3.0 公开候选验收、提交、推送及 GitHub Release 发布。
- 边界：不修改锁定公众号文章或私有母版；不跟踪、不打包私有 `scripts/build_cards.py`；不修改长期记忆；只提交并推送 LaborPilot 本轮公开文件。

## 本轮完成

- 将 `VERSION`、Plugin 清单、根 Skill、10 个专业 Skill、README 徽章、知识统计与评测数据统一为 `1.3.0`。
- 同步 `TASKS.md`、`AILOG.md` 和锁定文章能力审计的当前状态：GitHub 已发布 `v1.3.0`。
- 将“没签劳动合同”口语化召回纳入领域评测与变更日志；当前领域与法律版本评测为 18／18。
- 完成公开文件排除审查，并在 `.gitignore` 中排除本地配置、案件状态、产物目录、缓存、字节码和虚拟环境。
- 增加 `.github/workflows/release.yml`：仅在 `main` 的 `VERSION` 变更时，通过发布前测试后自动创建不可改写的 `v<version>` tag 及 GitHub Release。
- 为两个 GitHub Workflow 显式安装 Pandoc，保证真实 DOCX 与产物追溯测试可在 Ubuntu Runner 运行。
- 完成 README、快速上手、根 Skill、专业 Skill、契约文档、模板和任务痕迹的一致性审查。

## 验证证据

- Python 3.11 与 Python 3.12 本地全量测试：均为 70 项通过。
- 领域与法律版本评测：18／18 通过。
- `scripts/sync_version.py --check`：`1.3.0` 一致性通过。
- Plugin 整包校验、11 个 JSON 解析、Python 语法、高风险密钥模式和 `git diff --check`：均通过。
- Markdown 检查 37 个文件、15 个本地链接和 18 个脚本引用：0 断链，0 缺失脚本。
- 独立干净公开候选包：89 个文件，Python 3.12 的 70 项测试、18／18 评测、版本、Plugin、JSON、Python 语法和禁止项检查均通过。
- GitHub 双 Python CI 在提交 `54dd02485583d15a53ee5affa69d24b6a7fbf7c6` 上通过；自动发布工作流随后成功。
- `v1.3.0` 为 annotated tag，解析后指向 `54dd02485583d15a53ee5affa69d24b6a7fbf7c6`；GitHub Release 非草稿、非预发布。

## 发布结果

- 功能发布提交：`4c1013922f1857f2b5b500f6dddcaa32a3f9e875`；权限兼容修复：`f029952dff6ae9f61b7582e43da4ebcaefa4987d`；CI Pandoc 修复：`54dd02485583d15a53ee5affa69d24b6a7fbf7c6`。
- GitHub Release：`https://github.com/xxia-king/LaborPilot/releases/tag/v1.3.0`。
- 4 个 `.DS_Store`（含 `.git` 内 1 个 Finder 缓存）、2 个 `__pycache__` 目录及其中 24 个 `.pyc` 已移入废纸篓；清理后复查为 0。

## 后续更新

1. 普通代码或文档 push 只运行版本一致性检查，不创建 Release。
2. 发布新版本时同步更新 `VERSION` 和 `CHANGELOG.md`；推送到 `main` 后，发布工作流通过门禁才会创建对应的 `v<version>` tag 和 GitHub Release。
