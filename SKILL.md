---
name: portable-skills
description: Use when 用户说某个 skill 在别的 agent / harness 里看不到、要让 skill 跨 harness 通用或共享、把项目 skill 提到全局、同步各家的 skill 目录、或问「为什么 /xxx 在 DSH 里没有」；也用于排查重名遮蔽、命名被拒、软链方向反了。用户只要提到多个 agent（DSH、Claude Code、Codex、CodeBuddy）要共用同一个 skill，就用本 skill，即使没说「通用」二字。
---

# Portable Skills（跨 harness 通用 skill）

**一句话：一份真身，多处软链；先盘点，再链接，最后逐个 harness 验证。**

不同 agent 工具（harness）各扫各的目录，互不相通。所谓「让 skill 通用」，不是复制多份，而是**保留唯一真身，在其余 harness 的根目录里放指向它的符号链接**。复制多份必然分叉：改了 A 忘了 B，两台机器上还会互相覆盖。

## 0. 先记住三个事实

1. **每个 harness 只认自己那几个根**。`~/.claude/skills` 不是 DSH 的根，`~/.codex/skills` 也不是；只装一处，别处就是看不见。
2. **符号链接是通用解法**。DSH 发现时会跟随软链（`~/.agents/skills/tabbit` 就是先例），Claude Code、Codex 同样按目录读取；链接对它们等价于真目录。
3. **共享时采用单层技能单元**：`<root>/<name>/SKILL.md` 或工具支持的平铺 `<root>/<name>.md`。本脚本按直接子目录管理；嵌套扫描支持随 harness 不同，不能一概而论。

## 1. 根目录速查

| harness | 全局根 | 项目根 |
|---|---|---|
| **DSH** | `~/.dsh/skills`、`~/.agents/skills` | `<repo>/.dsh/skills`、`<repo>/.agents/skills` |
| **Claude Code** | `~/.claude/skills` | `<repo>/.claude/skills` |
| **Codex** | `~/.codex/skills` | `<repo>/.agents/skills`（未证实） |
| **CodeBuddy** | `~/.codebuddy/skills` | — |
| **WorkBuddy** | `~/.workbuddy/skills`（只接收，不回传） | — |

`~/.agents/skills` 是事实上的**公共枢纽**：DSH 扫它（rank 500），Codex 也读它，多个 CLI 把它当跨 runtime 别名。所以全局 skill 的真身优先放这里。

细节、优先级、验证方法与未证实项，见 [`references/harness-roots.md`](references/harness-roots.md)。

## 2. 决策：真身放哪

| 场景 | 真身位置 | 再链到 |
|---|---|---|
| 全局，所有 harness 都要 | `~/.agents/skills/<name>/` | `~/.dsh/skills`、`~/.claude/skills`、`~/.codex/skills`、`~/.codebuddy/skills` |
| 只给某一个项目 | `<repo>/.agents/skills/<name>/` | `<repo>/.claude/skills`、`<repo>/.dsh/skills` |
| 只给某一个 harness | 该 harness 自己的根 | 不链 |

判断口径只有一条：**这个 skill 是「我这台机器上都用」还是「这个仓库里才用」**。前者全局，后者跟着仓库走。

**链接方向只有一个：从各家根指向真身。** 反过来——让 `~/.agents/skills/<name>` 指向 `~/.claude/skills/<name>`——也能跑通，但真身就寄生在某个工具名下：那家改名、清理、重装，全部断链。

**WorkBuddy 是单向接收方（sink）**：其他 harness 的 skill 会链进 `~/.workbuddy/skills`，但它原有的 skill 不外流、不当真身。脚本把这类根单列，`--path` 指向它会被直接拒绝。

## 3. 标准流程

**先想清楚是哪一种活儿**：

- **全量对齐**（换了机器、装了新 harness、发现“某家的 skill 别家看不到”）→ 用 `sync`，一条命令把每个根里散落的 skill 收进枢纽并补齐链接，幂等，跑两遍第二遍零改动。
- **只装一个**（新建了一个 skill，或只想共享某一个）→ 用 `link`。

```bash
# 0) 全量对齐：任何根里的 skill → 枢纽真身 + 每个根一条软链
python3 scripts/skill_port.py sync --dry-run   # 先看它要搬什么、补哪些链
python3 scripts/skill_port.py sync

# 1) 盘点：这台机器上哪些 harness 有根、里面有什么、哪些是软链
python3 scripts/skill_port.py scan

# 2) 校验待装 skill：命名、frontmatter、目录一致性、体积
python3 scripts/skill_port.py check ~/.claude/skills/plain-talk

# 3) 只装一个：真身搬进 ~/.agents/skills，其余根自动建软链
python3 scripts/skill_port.py link plain-talk --path ~/.claude/skills/plain-talk --move

# 项目级（先 cd 进仓库）
python3 scripts/skill_port.py link my-skill --scope project

# 4) 回收：只删软链，绝不动真身
python3 scripts/skill_port.py unlink plain-talk --scope global
```

`sync` 遇到同名不同正文时**只报告、不动手**；`link` 是“我知道要装哪一个”，`sync` 是“把这台机器对齐”。

脚本一律先 `--dry-run` 看它会动哪里；不确定就直接跑 `scan`，只读不写。

搬完顺手看一眼正文：写死「本文件位于 `~/.claude/…`」这类旧路径的，改成相对描述或删掉——位置变了，正文里的旧说法就成了误导。

### 装完必须逐个验证

| harness | 验证方法 |
|---|---|
| DSH | 新开一轮对话看 skill 目录；或直接问「你有哪些 skill」。目录监听会自动刷新，无需重启 |
| Claude Code | `/skills` 面板；新会话里问一次 |
| Codex | 新开 session 看系统提示里的 skill 列表 |
| CodeBuddy | 重启或新会话，看 skill 列表 |

**验证不到就是没装成**，不要因为「目录里有软链」就宣布成功。

## 4. 冲突与红线

最常见的两个错：**用 `cp` 复制出多份**（立刻分叉）、**把枢纽链到某家目录**（真身寄生）。出现任一条，都算没做成。

- **目标已是真目录 / 真文件**：停手，报冲突，给用户三选一（改名、合并、放弃）。绝不覆盖、绝不删。
- **WorkBuddy 只进不出**：它的根是 sink，不是来源。别把它原有的 skill 链到别家，也别拿它当 canonical。
- **真要把 sink 里的 skill 转成公共 skill**：`link NAME --path <sink>/NAME --move --force` —— 真身搬进枢纽，再把链接发回 sink；不加 `--move` 会被拒绝。
- **目标已是指向别处的软链**：说明同一名字被两个真身争用；默认报冲突，用户明确要求才 `--force` 重链。
- **只删自己建的软链**：`unlink` 遇到真目录一律跳过并提示。
- **不写 App 内置 skill**：DSH 的 `office-skills` 在应用资源里，升级即覆盖；Claude 的 plugin cache 同理。要改就复制出来，链回去。
- **Windows**：没有开发者模式时普通用户建不了 symlink；退化为复制，并在 README 里写明「此处是副本，真身在 X」。当前主力环境是 macOS，不涉及。
- **别把密钥、token、私人路径写进 skill**——它会随仓库或同步工具扩散。

## 5. 命名与 frontmatter（硬约束）

```yaml
---
name: my-skill            # 必填；kebab-case，全小写
description: ...          # 必填；≤500 字符（DSH 目录会截断）
---
```

- `name` 必须匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`：小写字母/数字，单词间单个连字符；大写、下划线、点、中文、连续连字符一律不合格。
- **`name` 与目录名保持一致**。DSH 以 frontmatter 为准、目录名只负责定位；Claude Code 把 `.claude/skills/*` 当目录插件加载，名字歧义会直接报冲突。一致最省事。
- `description` 是唯一的触发依据：写清「什么时候用」，别写「这是一个用于……的 skill」。
- **只用跨 harness 通用的键**（`name`、`description`、`version`、`license`、`metadata`）。各家私有键在别处会被忽略甚至报错，宁可不写。
- 正文控制在 500 行内；长文档放 `references/`，脚本放 `scripts/`，模板放 `assets/`。资源一律用**相对 SKILL.md 的路径**引用，别假设 cwd。

## 6. 排查「某个 harness 看不到这个 skill」

按顺序过，命中即停：

1. **根对不对**：查第 1 节表；`scan` 会告诉你这个 harness 的根在哪、是否为空。
2. **目录层级不匹配**：本脚本按 `<root>/<name>/SKILL.md` 管理。深层目录是否能被加载取决于 harness；共享时优先使用直接子目录。
3. **名字被拒**：跑 `check`，看 kebab-case 与 frontmatter 是否完整。DSH 对坏 frontmatter 是**静默丢弃**，日志里才有 warn。
4. **被同名遮蔽**：同一名字在多个根出现时，低 rank 的会被丢弃（DSH 项目级 > 用户级，`~/.dsh` > `~/.agents`）。
5. **没刷新**：DSH 会自动刷新目录，但仍需下一轮对话才吃得到；Claude Code / Codex 通常要新会话。
6. **装错层**：项目 skill 在 A 仓库，却在 B 仓库里找。项目根按最近的 `.git` 祖先判定，嵌套仓库会改变判定结果。

## 7. 命令一览

| 命令 | 作用 |
|---|---|
| `sync [--dry-run] [--force]` | 全量对齐：任何根里的 skill 都收进枢纽，再补齐每个根的链接；幂等 |
| `link NAME [--path DIR] [--move] [--force]` | 只装一个；`--move` 把真身搬进枢纽 |
| `unlink NAME` | 只删软链，不碰真身 |
| `scan` | 只读盘点各根现状 |
| `check DIR` | 校验命名、frontmatter、目录一致性 |
| `roots` | 列出各 harness 的根与是否存在 |

这份 skill 自己也是这么装的：真身在 `~/.agents/skills/portable-skills/`，其余根里都是指向它的软链。改内容只改真身一处。

## 8. 参考

- [`references/harness-roots.md`](references/harness-roots.md) —— 各 harness 的根、优先级、证据与「未证实」标注
- `scripts/skill_port.py` —— `roots` / `scan` / `check` / `link` / `unlink`
