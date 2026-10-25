# WorkBuddy 专家版交接

## 开发入口

```bash
git clone --branch workbuddy https://github.com/xxia-king/LaborPilot.git laborpilot
cd laborpilot
git status --short --branch
```

维护者使用 Git clone 获取源码和维护文档；`git archive` 及 GitHub 的源码 ZIP 会按照 `.gitattributes` 排除维护记录。

`main` 提供普通插件；`workbuddy` 长期维护 WorkBuddy 专家渠道适配。通用引擎更新由主线同步到专家分支；平台清单、提示词和头像保留在专家分支。

## 已完成与验证边界

- 专家版基于公开版本 1.4.4，首次适配提交为 `437945e`。
- 清单引用现有 10 个 Skill；专家标识、Agent 文件名和包根目录统一为 `laborpilot`。
- 官方结构校验与打包通过；首次适配的 81 项本地回归测试以及 GitHub Python 3.11、3.12 检查通过。
- 原包备份、详细核验记录和清理恢复清单由维护者在本地保存。
- 本会话未再次上传 WorkBuddy 官网或验证新包在 WorkBuddy 中的加载与任务运行；该项保留在任务清单中。

## 维护文档与交付包

- [TASKS.md](../../TASKS.md) 是任务状态的唯一维护入口；[AILOG.md](../../AILOG.md) 保存精简 AI 参与记录。
- [CHANGELOG.md](../../CHANGELOG.md) 记录项目变更；本文件负责接续方式与验证边界。
- 根级 `TASKS.md`、`AILOG.md` 和 `docs/maintenance/` 通过 `.gitattributes` 标记 `export-ignore`。
- 必须按 [专家适配说明](../WORKBUDDY.md) 从指定 Git 提交导出，再运行官方打包器；直接压缩工作目录不会应用 Git 的归档排除规则。
- 案件资料、密钥、本机日志、原包备份及缓存不纳入公开仓库。

## 后续工作

先核对当前分支、工作区与主线变化，再执行任务。需要升级专家版时，同步所需主线变更，核对 `VERSION` 与专家清单版本，重新校验并打包。当前 `sync_version.py` 是否覆盖专家清单，应在首次升级时另行核验。

每次维护同步任务状态、AI 台账及必要的交接信息；涉及法律口径的改动另行核验效力与律师审批，不以技术测试代替业务审定。
