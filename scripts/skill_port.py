#!/usr/bin/env python3
"""skill-port: one physical skill, visible to every agent harness on this machine.

Model: a skill body lives in exactly one real directory; every other harness
root gets a symlink pointing at it. Nothing is copied, nothing is overwritten.

Commands
    roots                       show harness roots and whether they exist
    scan                        inventory every root (read-only)
    check DIR                   validate a skill directory
    link NAME [--path DIR]      create symlinks for NAME in every root
    unlink NAME                 remove only the symlinks this tool would create

Scope
    --scope global   (~/.agents/skills, ~/.dsh/skills, ~/.claude/skills, ...)
    --scope project  (<repo>/.agents/skills, <repo>/.dsh/skills, ...)

Sink roots (~/.workbuddy/skills) receive links only. They are never used as a
source: nothing in a sink is promoted back out to the other harnesses.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HOME = Path.home()

GLOBAL_ROOTS = [
    ("agents", HOME / ".agents" / "skills"),
    ("dsh", HOME / ".dsh" / "skills"),
    ("claude", HOME / ".claude" / "skills"),
    ("codex", HOME / ".codex" / "skills"),
    ("codebuddy", HOME / ".codebuddy" / "skills"),
]

PROJECT_RELS = [
    ("agents", ".agents/skills"),
    ("dsh", ".dsh/skills"),
    ("claude", ".claude/skills"),
]

# Receive-only roots: other harnesses push links here, but nothing here is ever
# promoted back out. WorkBuddy owns its own skills; we only make ours visible to it.
SINK_ROOTS = [
    ("workbuddy", HOME / ".workbuddy" / "skills"),
]


# --------------------------------------------------------------------------- io


def repo_root():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except OSError:
        pass
    return Path.cwd()


def roots_for(scope):
    if scope == "global":
        return [(label, path) for label, path in GLOBAL_ROOTS]
    base = repo_root()
    return [(label, base / rel) for label, rel in PROJECT_RELS]


def canonical_for(scope):
    for label, path in roots_for(scope):
        if label == "agents":
            return path
    raise SystemExit("internal: no canonical root for scope " + scope)


def sinks_for(scope):
    """Receive-only roots; global only, never a source of truth."""
    return list(SINK_ROOTS) if scope == "global" else []


def pretty(path):
    try:
        return "~/" + str(path.relative_to(HOME))
    except ValueError:
        return str(path)


def read_frontmatter(skill_file):
    """Minimal YAML frontmatter reader: top-level scalars plus simple blocks."""
    try:
        text = skill_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    data, key = {}, None
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            if value in (">", "|", ">-", "|-", ">+", "|+"):
                value = ""
            data[key] = value.strip("'\"")
        elif key and line[:1] in (" ", "\t"):
            data[key] = (data.get(key, "") + " " + line.strip()).strip()
    return data


# ---------------------------------------------------------------------- inspect


def describe(entry):
    """Return (name, kind, display_target, note, real_path) for a root entry."""
    if entry.is_symlink():
        if not entry.exists():
            return (entry.name, "broken", str(os.readlink(entry)), "软链指向不存在", None)
        target = entry.resolve()
        if target.is_file():
            return (entry.stem, "flat", str(target), "", str(target))
        return (entry.name, "link", str(target),
                _note(entry.name, target / "SKILL.md", target), str(target))

    if entry.is_dir():
        return (entry.name, "dir", "-",
                _note(entry.name, entry / "SKILL.md", entry), str(entry.resolve()))

    if entry.is_file() and entry.suffix == ".md":
        return (entry.stem, "flat", "-", "", str(entry.resolve()))

    return None


def _note(dir_name, skill_file, body_dir):
    if not skill_file.is_file():
        return "无 SKILL.md（不是 skill）"
    fm = read_frontmatter(skill_file)
    name = fm.get("name", "")
    notes = []
    if not name:
        notes.append("缺 frontmatter name")
    elif not NAME_RE.match(name):
        notes.append("name 非 kebab-case")
    elif name != dir_name:
        notes.append("name≠目录名")
    if not fm.get("description"):
        notes.append("缺 description")
    return "; ".join(notes)


def cmd_roots(args):
    for scope in ("global", "project"):
        print("[%s]" % scope)
        for label, path in roots_for(scope):
            state = "存在" if path.is_dir() else "不存在"
            count = len([p for p in path.iterdir()]) if path.is_dir() else 0
            print("  %-10s %-34s %s%s" % (
                label, pretty(path), state,
                "（%d 项）" % count if path.is_dir() else "",
            ))
        for label, path in sinks_for(scope):
            state = "存在" if path.is_dir() else "不存在"
            count = len([p for p in path.iterdir()]) if path.is_dir() else 0
            print("  %-10s %-34s %s%s  ← 只接收，不回传" % (
                label, pretty(path), state,
                "（%d 项）" % count if path.is_dir() else "",
            ))
    if args.scope == "project":
        print("\n项目根：%s" % repo_root())


def _print_root(label, root, seen=None, suffix=""):
    print("\n[%s] %s%s" % (label, pretty(root), suffix))
    if not root.is_dir():
        print("  （根不存在）")
        return
    rows = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        info = describe(entry)
        if info is None:
            continue
        name, kind, target, note, real = info
        rows.append((name, kind, target, note))
        if seen is not None:
            seen.setdefault(name, []).append((label, real))
    if not rows:
        print("  （空）")
        return
    width = max(len(r[0]) for r in rows)
    for name, kind, target, note in rows:
        line = "  %-*s  %-6s" % (width, name, kind)
        if target != "-":
            line += "  " + target
        if note:
            line += "  ← " + note
        print(line)


def cmd_scan(args):
    seen = {}
    for label, root in roots_for(args.scope):
        _print_root(label, root, seen)
    for label, root in sinks_for(args.scope):
        _print_root(label, root, None, suffix="（只接收，不回传）")

    # A name repeated across roots is only a problem when the bodies differ;
    # links to one shared body are the intended setup.
    shadowed = {}
    for name, hits in seen.items():
        bodies = {real for _, real in hits if real is not None}
        if len(bodies) > 1:
            shadowed[name] = hits
    if shadowed:
        print("\n同名但真身不同（只有一个会生效，其余被遮蔽）：")
        for name, hits in sorted(shadowed.items()):
            print("  %s" % name)
            for label, real in hits:
                print("    %-10s %s" % (label, real))
    return 0


def cmd_check(args):
    raw = Path(args.path).expanduser()
    if raw.is_symlink():
        print("软链 → %s" % raw.resolve())
    path = raw.resolve()
    if path.is_file():
        issues = []
        fm = read_frontmatter(path)
        if not NAME_RE.match(fm.get("name", "")):
            issues.append("name 缺失或非 kebab-case")
        if not fm.get("description"):
            issues.append("缺 description")
        print(_report(path, issues, []))
        return 1 if issues else 0
    if not path.is_dir():
        print("✗ 路径不存在：%s" % path)
        return 1

    skill_file = path / "SKILL.md"
    issues, warns = [], []
    if not skill_file.is_file():
        issues.append("目录里没有 SKILL.md（发现深度只到 <root>/<name>/SKILL.md）")
    else:
        fm = read_frontmatter(skill_file)
        name = fm.get("name", "")
        desc = fm.get("description", "")
        if not name:
            issues.append("frontmatter 缺 name")
        elif not NAME_RE.match(name):
            issues.append("name 不合 kebab-case：%r" % name)
        elif name != path.name:
            warns.append("name(%s) ≠ 目录名(%s)" % (name, path.name))
        if not desc:
            issues.append("frontmatter 缺 description")
        elif len(desc) > 500:
            warns.append("description %d 字符，超过目录展示上限 500（会被截断）" % len(desc))
        lines = len(skill_file.read_text(encoding="utf-8", errors="replace").splitlines())
        if lines > 500:
            warns.append("SKILL.md %d 行，偏长（建议 <500，正文外置到 references/）" % lines)

    print(_report(path, issues, warns))
    return 1 if issues else 0


def _report(path, issues, warns):
    out = ["检查：%s" % path]
    for w in warns:
        out.append("  ⚠ " + w)
    for i in issues:
        out.append("  ✗ " + i)
    if not issues:
        out.append("  ✓ 可以安装")
    return "\n".join(out)


# ------------------------------------------------------------------------- link


def _resolve_source(args, scope):
    canon = canonical_for(scope)
    if args.path:
        src = Path(args.path).expanduser()
        if not src.exists():
            raise SystemExit("✗ --path 不存在：%s" % src)
        src = src.resolve()          # absolute, symlinks followed
        if not src.is_dir():
            raise SystemExit("✗ --path 不是目录：%s" % src)
        if args.name and args.name != src.name:
            raise SystemExit(
                "✗ --path 指向 %s，但 NAME 是 %s；名字要改请先改目录名与 frontmatter"
                % (src.name, args.name))
        return src.name, src, canon

    if not args.name:
        raise SystemExit("✗ 需要 NAME，或用 --path 指定 skill 目录")
    name = args.name
    src = canon / name
    if src.is_dir():
        return name, src.resolve(), canon

    for label, root in roots_for(scope):
        cand = root / name
        if cand.is_dir():
            return name, cand.resolve(), canon
    raise SystemExit("✗ 找不到 skill：%s（可加 --path 指定）" % name)


def cmd_link(args):
    scope = args.scope
    name, src, canon = _resolve_source(args, scope)
    if not NAME_RE.match(name):
        raise SystemExit("✗ 名字不合 kebab-case：%r" % name)
    if not (src / "SKILL.md").is_file():
        raise SystemExit("✗ %s 里没有 SKILL.md" % src)
    for label, sink in sinks_for(scope):
        if (src == sink or sink in src.parents) and not args.move:
            raise SystemExit(
                "✗ %s 只接收、不回传，不能当作真身来源：%s\n"
                "  确实要把它提成公共 skill，用 --move 搬进枢纽（会从 %s 移走）"
                % (label, pretty(src), label))

    if args.move and src != (canon / name).resolve():
        dest = canon / name
        if dest.exists():
            raise SystemExit("✗ 目标已存在，不能移动：%s" % dest)
        if args.dry_run:
            print("would move %s → %s" % (src, dest))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)
            print("moved %s → %s" % (src, dest))
        src = dest.resolve()

    print("真身：%s" % src)
    failures = 0
    for label, root in roots_for(scope) + sinks_for(scope):
        target = root / name
        if target.is_symlink() and target.resolve() == src:
            print("  %-10s 已就位" % label)
            continue
        if target.resolve() == src and target.exists():
            print("  %-10s 已是真身" % label)
            continue
        if target.is_symlink():
            if not args.force:
                print("  %-10s ✗ 已链接到别处：%s（加 --force 重链）" % (label, target.resolve()))
                failures += 1
                continue
            if args.dry_run:
                print("  %-10s would relink" % label)
            else:
                target.unlink()
                target.symlink_to(src, target_is_directory=True)
                print("  %-10s 已重链" % label)
            continue
        if target.exists():
            print("  %-10s ✗ 已存在同名真实内容：%s（不覆盖）" % (label, target))
            failures += 1
            continue
        if args.dry_run:
            print("  %-10s would link" % label)
        else:
            root.mkdir(parents=True, exist_ok=True)
            target.symlink_to(src, target_is_directory=True)
            print("  %-10s 已链接" % label)

    if failures:
        print("\n有冲突未处理；确认后可用 --force 或手动改名。")
        return 1
    return 0


def cmd_unlink(args):
    name = args.name
    removed = 0
    for label, root in roots_for(args.scope) + sinks_for(args.scope):
        target = root / name
        if target.is_symlink():
            dest = os.readlink(target)
            if args.dry_run:
                print("  %-10s would remove → %s" % (label, dest))
            else:
                target.unlink()
                print("  %-10s removed → %s" % (label, dest))
            removed += 1
        elif target.exists():
            print("  %-10s 跳过：真实目录，不删（%s）" % (label, target))
    if removed == 0:
        print("没有可删的软链。")
    return 0


# ------------------------------------------------------------------------- sync


def _collect_skills(roots):
    """Group every real skill directory by name across the given roots."""
    found = {}
    for label, root in roots:
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith(".") or not entry.exists():
                continue
            real = entry.resolve()
            if not (real / "SKILL.md").is_file():
                continue
            found.setdefault(entry.name, []).append((label, real))
    return found


def _ensure_links(name, src, scope, dry, force, skip_label=None):
    """Return (labels touched, failures); skip_label simulates an already-freed root."""
    touched, failed = [], 0
    for label, root in roots_for(scope) + sinks_for(scope):
        if label == skip_label:
            continue
        target = root / name
        if target.is_symlink() and target.resolve() == src:
            continue
        if not target.is_symlink() and target.exists() and target.resolve() == src:
            continue
        if target.is_symlink():
            if not force:
                print("  %-10s ✗ 已指向 %s（--force 重链）" % (label, pretty(target.resolve())))
                failed += 1
                continue
            if not dry:
                target.unlink()
                target.symlink_to(src, target_is_directory=True)
            touched.append(label)
            continue
        if target.exists():
            print("  %-10s ✗ 已存在真实内容（不覆盖）" % label)
            failed += 1
            continue
        if not dry:
            root.mkdir(parents=True, exist_ok=True)
            target.symlink_to(src, target_is_directory=True)
        touched.append(label)
    return touched, failed


def cmd_sync(args):
    """Enroll every skill found in any root: one body in the hub, links elsewhere."""
    scope = "global"
    hub = canonical_for(scope)
    found = _collect_skills(roots_for(scope))
    moved = linked = problems = 0
    for name in sorted(found):
        hits = found[name]
        bodies = {str(real) for _, real in hits}
        if len(bodies) > 1:
            print("%-26s ✗ 同名多真身，跳过：%s" % (
                name, " | ".join(sorted(pretty(Path(b)) for b in bodies))))
            problems += 1
            continue
        if not NAME_RE.match(name):
            print("%-26s ✗ 名字不合 kebab-case，跳过" % name)
            problems += 1
            continue
        src = Path(next(iter(bodies)))
        skip = None
        note = ""
        if (hub / name).exists() and (hub / name).resolve() == src:
            src = (hub / name).resolve()
        elif src.parent != hub:
            dest = hub / name
            if dest.exists():
                print("%-26s ✗ 枢纽已有同名，跳过" % name)
                problems += 1
                continue
            if args.dry_run:
                skip = next((l for l, r in roots_for(scope) if r == src.parent), None)
            if args.dry_run:
                note = "↑ 会从 %s 搬进枢纽" % pretty(src.parent)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dest)
                note = "↑ 已从 %s 搬进枢纽" % pretty(src.parent)
            src = dest
            moved += 1
        touched, failed = _ensure_links(name, src, scope, args.dry_run, args.force, skip)
        linked += len(touched)
        problems += failed
        if note or touched or failed:
            detail = ("，补链 " + "/".join(touched)) if touched else ""
            print("%-26s %s%s" % (name, note or "已在枢纽", detail))
    print("\n汇总：搬动 %d，新建/修复链接 %d，跳过或冲突 %d%s" % (
        moved, linked, problems, "（dry-run，未落盘）" if args.dry_run else ""))
    return 1 if problems else 0


# ------------------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(prog="skill_port.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("roots", help="show harness roots")
    p.add_argument("--scope", choices=["global", "project"], default="global")
    p.set_defaults(func=cmd_roots)

    p = sub.add_parser("scan", help="inventory every root (read-only)")
    p.add_argument("--scope", choices=["global", "project"], default="global")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("check", help="validate a skill directory")
    p.add_argument("path")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("link", help="symlink NAME into every root")
    p.add_argument("name", nargs="?")
    p.add_argument("--path", help="real skill directory (default: <canonical>/NAME)")
    p.add_argument("--scope", choices=["global", "project"], default="global")
    p.add_argument("--move", action="store_true", help="move --path into the canonical root first")
    p.add_argument("--force", action="store_true", help="replace a symlink that points elsewhere")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("sync", help="enroll every skill: one body in the hub, links everywhere")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("unlink", help="remove only symlinks named NAME")
    p.add_argument("name")
    p.add_argument("--scope", choices=["global", "project"], default="global")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_unlink)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
