# Harness 根目录与优先级

> 本文件是 `portable-skills` 的参考件。**标「已验证」的来自源码或本机实测；标「未证实」的是推断，动手前自己验一遍。**

## 通用模型

一个 skill = 一个目录 + `SKILL.md`（或平铺的 `<name>.md`）。发现规则在几乎所有 harness 上一致：

- 跨工具共享采用直接子目录：`<root>/<name>/SKILL.md`；嵌套目录支持随工具不同，不能统一假定。
- 文件以 YAML frontmatter 开头，`name` + `description` 必填
- `name` 基本都要求 kebab-case
- 重名时按「项目级 > 用户级」「靠前根 > 靠后根」取一个，其余被遮蔽

差异只在**根目录列表**和**个别私有键**。

## 矩阵

| harness | 全局根（按优先级） | 项目根 | 深度 | 依据 |
|---|---|---|---|---|
| **DSH** | `~/.dsh/skills` → `~/.agents/skills` | `<repo>/.dsh/skills` → `<repo>/.agents/skills` | 1 | 已验证（源码） |
| **Claude Code** | `~/.claude/skills` | `<repo>/.claude/skills` | 1 | 已验证（二进制字符串） |
| **Codex** | `~/.codex/skills` | `<repo>/.agents/skills`（未证实） | 1 | 部分验证 |
| **CodeBuddy** | `~/.codebuddy/skills` | `<repo>/.codebuddy/skills`（产品支持；本脚本尚未管理） | 按产品规则 | [官方技能文档](https://www.codebuddy.cn/docs/cli/skills) |
| **WorkBuddy** | `~/.workbuddy/skills` —— **只接收，不回传** | — | 1 | 目录与格式实测；扫描路径未直接验证 |
| Gemini CLI / Copilot CLI | `~/.agents/skills`（未证实） | — | 1 | 未证实 |

WorkBuddy 的单向规则是用户口径：其他 harness 的 skill 可以链进去，但它已有的 skill（`meeting-minutes`、`workbuddy-*` 等）不外流、不当真身。脚本把它归为 **sink**：`link` 会往里链，`scan` 单列显示，`--path` 指向它直接报错。

DSH 的完整 rank 表（含 `customSkillDirs` 与内置根，数值越小越优先）：

| rank | 路径 |
|---|---|
| 100 | `<repo>/.dsh/skills` |
| 200 | `<repo>/.agents/skills` |
| 250 | runtime 注册（插件内建） |
| 300 | `customSkillDirs` |
| 400 | `~/.dsh/skills` |
| 500 | `~/.agents/skills` |
| 600 | 内置 bundled 根（如 App 的 `office-skills`） |

- **项目根 = 最近的含 `.git` 的祖先**；嵌套仓库会改变判定。
- **重名**：同层内 rank 小者胜，其余 warn + 丢弃。
- **命名**：`^[a-z0-9]+(?:-[a-z0-9]+)*$`（`dsh-skill/lib/index.js`）。
- **软链**：发现时跟随（`nodeEntryKind` 对 symlink 做 `stat`），所以 `~/.agents/skills/tabbit -> Tabbit App 内目录` 可用。
- **生效时机**：新增/改名/删除/改 frontmatter 在下一模型步刷新；正文每次 load 重读。
- 坏 frontmatter 或非法名字：**静默丢弃**，只在宿主日志留 warn。

## 证据

**DSH**（源码，权威）
- `@deepseek-ai/dsh-skill-filesystem/README.zh.md`：根列表、优先级、深度 1、frontmatter 规则
- `@deepseek-ai/dsh-skill-filesystem/lib/index.js`：`discoverRoot` / `nodeEntryKind`（symlink 跟随）
- `@deepseek-ai/dsh-skill/lib/index.js:17`：`SKILL_NAME` 正则
- `@deepseek-ai/dsh-tool-skill/lib/index.js`：目录描述 500 字符截断（`catalogDescriptionMaxLength`）

**Claude Code**（v2.1.241 二进制字符串）
- 出现 `.claude/skills/`、`~/.claude/skills/`
- 出现 `Skills-directory plugins (.claude/skills/*)`：`.claude/skills/*` 目录会被当作目录插件加载
- 未出现 `~/.agents/skills`，故**不认为** Claude Code 读该别名

**Codex**（`~/.local/bin/codex` 二进制 + 本机配置）
- 二进制出现 `.agents/skills` 与 `.codex/skills`
- `~/.codex/skills/` 实存（含 `.system/`、`find-skills/` 等）
- `~/.codex/AGENTS.md` 直接引用 `~/.agents/skills/dingtalk-chat/SKILL.md`，说明它确实读公共枢纽

**CodeBuddy**
- `~/.codebuddy/skills/` 实存，内含与 DSH 同名同格式的 `dingtalk-*` 系列（frontmatter 一致），说明格式互通

## 未证实项（动手前先验）

1. Codex 的**项目级**根到底是 `<repo>/.agents/skills` 还是 `<repo>/.codex/skills` —— 二进制里两者都出现，未定位到判定逻辑。
2. Gemini CLI / Copilot CLI 是否读 `~/.agents/skills` —— 来自第三方 skill 文档的说法，本机无对应目录可验。
3. Claude Code 对 `~/.agents/skills` 的支持 —— 当前版本二进制里没有该路径，**当它不读**。

验证办法（通用）：把 skill 放进候选根 → 新开会话 → 让对方列出自己的 skill，或看它的 `/skills` 面板。列不出来就是没读到。

## Hermes 与共享目录

Hermes 支持在 `~/.hermes/config.yaml` 的 `skills.external_dirs` 中配置 `~/.agents/skills`，因此可直接共用公共目录中的技能。项目级支持 `.hermes/skills` 和 `.agents/skills`，需要先信任项目。本脚本没有自动修改 Hermes 配置，也没有管理其独立目录。

```yaml
skills:
  external_dirs:
    - ~/.agents/skills
```

依据：[Hermes 官方技能系统](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#external-skill-directories)。各产品加载行为会随版本变化，最终以对应工具的技能列表实测为准。
