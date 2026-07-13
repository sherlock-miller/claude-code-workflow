#!/usr/bin/env python3
"""周报自动生成器 — 基于 Git 提交记录。"""

import argparse
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta


def run_git(git_dir: str, args: list) -> str:
    """在指定 git 目录中执行 git 命令。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=git_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return ""


def get_weekly_commits(git_dir: str, days: int = 7) -> list:
    """获取最近 N 天的提交记录。"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    output = run_git(git_dir, [
        "log",
        f"--since={since}",
        "--pretty=format:%H|%an|%ad|%s",
        "--date=short",
    ])
    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0][:8],
                "author": parts[1],
                "date": parts[2],
                "message": parts[3],
            })
    return commits


def get_changed_files(git_dir: str, days: int = 7) -> list:
    """获取最近变更的文件列表。"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    output = run_git(git_dir, ["diff", "--name-only", f"--since={since}", "HEAD"])
    if not output:
        return []
    return list(set(output.split("\n")))


def get_stats(git_dir: str, days: int = 7) -> dict:
    """获取提交统计。"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    output = run_git(git_dir, ["log", f"--since={since}", "--pretty=format:%an", "--numstat"])
    additions = 0
    deletions = 0
    author_counts = defaultdict(int)

    for line in output.split("\n"):
        parts = line.split("\t")
        if len(parts) == 3:
            try:
                additions += int(parts[0])
                deletions += int(parts[1])
            except ValueError:
                pass

    commits = get_weekly_commits(git_dir, days)
    for c in commits:
        author_counts[c["author"]] += 1

    return {
        "total_commits": len(commits),
        "additions": additions,
        "deletions": deletions,
        "authors": dict(author_counts),
    }


def generate_report(project: str, git_dir: str, days: int = 7, custom_items: str = ""):
    """生成周报 Markdown 内容。"""
    today = datetime.now()
    week_start = today - timedelta(days=days)
    commits = get_weekly_commits(git_dir, days)
    files = get_changed_files(git_dir, days)
    stats = get_stats(git_dir, days)

    report = f"""# {project} — 周报

**周期**: {week_start.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}

## 概览

| 指标 | 数值 |
|------|------|
| 提交次数 | {stats['total_commits']} |
| 新增行数 | +{stats['additions']} |
| 删除行数 | -{stats['deletions']} |
| 变更文件 | {len(files)} |

## 贡献者

"""
    for author, count in stats["authors"].items():
        report += f"- **{author}**: {count} 次提交\n"

    report += "\n## 本周提交\n\n"
    for c in commits:
        report += f"- [{c['date']}] {c['message']} (`{c['hash']}` — {c['author']})\n"

    if files:
        report += "\n## 变更文件\n\n"
        for f in sorted(files)[:30]:  # 最多显示 30 个
            report += f"- `{f}`\n"
        if len(files) > 30:
            report += f"- ... 以及其他 {len(files) - 30} 个文件\n"

    report += """
## 工作详情

### 本周完成
- （请在此补充具体完成的工作内容）

### 遇到的问题
- （请在此补充遇到的阻塞或问题）

### 下周计划
- （请在此补充下周计划）

"""
    if custom_items:
        report += f"\n## 补充说明\n\n{custom_items}\n"

    report += f"\n> 🤖 自动生成于 {today.strftime('%Y-%m-%d %H:%M')}，数据来源: Git 提交记录"
    return report


def main():
    parser = argparse.ArgumentParser(description="周报生成器")
    parser.add_argument("--project", required=True, help="项目名称")
    parser.add_argument("--git-dir", default=".", help="Git 仓库目录（默认当前目录）")
    parser.add_argument("--days", type=int, default=7, help="统计天数（默认7）")
    parser.add_argument("--extra", help="补充说明内容")
    parser.add_argument("--output", help="输出文件路径（默认打印到终端）")
    args = parser.parse_args()

    if not os.path.isdir(os.path.join(args.git_dir, ".git")):
        print(f"错误：'{args.git_dir}' 不是一个 Git 仓库")
        sys.exit(1)

    report = generate_report(args.project, args.git_dir, args.days, args.extra)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"📄 周报已保存到: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
