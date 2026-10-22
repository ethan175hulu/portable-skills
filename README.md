# portable-skills

一份技能真身，多处软链接：在多个agent运行环境之间共享 `SKILL.md`、参考文件和脚本，减少重复副本与内容分叉。

## 安装

Python 3.10+，仅使用标准库。主要面向支持符号链接的 macOS / Linux 环境；Windows 的链接权限与宿主加载情况需要另外验证。

```bash
# 目标目录须不存在；如果已经安装，请先检查原有目录
mkdir -p ~/.agents/skills
git clone https://github.com/ethan175hulu/portable-skills.git ~/.agents/skills/portable-skills
python3 ~/.agents/skills/portable-skills/scripts/skill_port.py check ~/.agents/skills/portable-skills
```

## 实际覆盖范围

| 工具 | 脚本管理范围 |
|---|---|
| DSH | 全局与项目级 |
| Claude Code | 全局与项目级 |
| Codex | 全局；项目级使用公共 `.agents/skills` 入口，以加载验证为准 |
| CodeBuddy | 全局；产品支持的项目级 `.codebuddy/skills` 尚未加入脚本目录列表 |
| WorkBuddy | 全局接收端，其他技能可共享进来，自有技能默认不向外迁移 |
| Hermes Agent | 可配置读取公共 `~/.agents/skills`；脚本不自动修改 Hermes 配置 |

WorkBuddy 的单向处理是本脚本的保护策略。目录共享解决技能发现和文件复用；执行时仍取决于宿主具备的工具、权限及多agent能力。

## 先预览，再执行

以下命令在仓库根目录运行；也可使用 `scripts/skill_port.py` 的完整路径。

```bash
# 只读盘点
python3 scripts/skill_port.py roots
python3 scripts/skill_port.py scan

# 单个技能：先检查和预览
python3 scripts/skill_port.py check ~/.agents/skills/page-prompt-adapt
python3 scripts/skill_port.py link page-prompt-adapt --dry-run

# 预览正确后再执行
python3 scripts/skill_port.py link page-prompt-adapt

# 全量对齐同样先预览；实际 sync 会将散落技能搬入公共目录
python3 scripts/skill_port.py sync --dry-run
python3 scripts/skill_port.py sync
```

已有真实目录不会被覆盖，同名不同真身会报告冲突。`unlink` 删除指定名称的符号链接，保留真实目录；执行前同样先用 `--dry-run` 查看目标。

## Hermes 共享目录

按 [Hermes 官方说明](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#external-skill-directories)，可在现有配置中合并：

```yaml
skills:
  external_dirs:
    - ~/.agents/skills
```

配置好后，用 Hermes 的技能列表验证是否识别。项目技能还需按 Hermes 的项目信任规则启用。本仓库不会自行修改这些配置。

## 文件

- [SKILL.md](SKILL.md)：使用规则、共享方式和冲突边界。
- [scripts/skill_port.py](scripts/skill_port.py)：roots / scan / check / link / unlink / sync。
- [references/harness-roots.md](references/harness-roots.md)：目录依据、适配差别与待验证项。

## 公开版本整理

保留原有脚本行为；移除私人绝对路径和本机技能数量快照，并补充共享目录及当前覆盖范围说明。实际可见性请逐个运行环境验证。
