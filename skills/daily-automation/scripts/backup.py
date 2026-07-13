#!/usr/bin/env python3
"""文件夹增量备份工具。"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime


def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def hash_file(filepath: str) -> str:
    """计算文件 MD5 哈希用于比较变更。"""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""


def load_snapshot(snapshot_file: str) -> dict:
    """加载上次备份的文件快照。"""
    if os.path.exists(snapshot_file):
        with open(snapshot_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_snapshot(snapshot_file: str, snapshot: dict):
    os.makedirs(os.path.dirname(snapshot_file) if os.path.dirname(snapshot_file) else ".", exist_ok=True)
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def should_exclude(filepath: str, excludes: list) -> bool:
    for pattern in excludes:
        if pattern in filepath.replace("\\", "/"):
            return True
    return False


def backup(source: str, target: str, excludes: list, max_versions: int):
    """执行增量备份。"""
    if not os.path.isdir(source):
        print(f"错误：源目录 '{source}' 不存在")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(target, f"backup_{timestamp}")
    snapshot_file = os.path.join(target, ".backup_snapshot.json")

    old_snapshot = load_snapshot(snapshot_file)
    new_snapshot = {}
    stats = {"copied": 0, "unchanged": 0, "skipped": 0, "total_size": 0}

    print(f"\n📦 备份: {source} → {backup_dir}\n")

    for root, dirs, files in os.walk(source):
        # 过滤排除的目录
        dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d) + "/", excludes)]

        for fname in files:
            src_path = os.path.join(root, fname)
            rel_path = os.path.relpath(src_path, source).replace("\\", "/")

            if should_exclude(rel_path, excludes):
                stats["skipped"] += 1
                continue

            try:
                current_hash = hash_file(src_path)
                new_snapshot[rel_path] = current_hash

                if rel_path in old_snapshot and old_snapshot[rel_path] == current_hash:
                    stats["unchanged"] += 1
                    continue

                # 需要复制
                dest_path = os.path.join(backup_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
                stats["copied"] += 1
                stats["total_size"] += os.path.getsize(src_path)
                print(f"  ✓ {rel_path}")
            except OSError as e:
                print(f"  ✗ {rel_path}: {e}")
                stats["skipped"] += 1

    # 保存新快照
    save_snapshot(snapshot_file, new_snapshot)

    # 清理旧备份（保留最近 N 个版本）
    backups = sorted([d for d in os.listdir(target) if d.startswith("backup_")], reverse=True)
    for old_backup in backups[max_versions:]:
        old_path = os.path.join(target, old_backup)
        if os.path.isdir(old_path):
            shutil.rmtree(old_path)
            print(f"  🗑 已清理旧备份: {old_backup}")

    # 报告
    print(f"\n✅ 备份完成！")
    print(f"   新增/修改: {stats['copied']} 个文件 ({format_size(stats['total_size'])})")
    print(f"   未变化:   {stats['unchanged']} 个文件")
    print(f"   已跳过:   {stats['skipped']} 个文件")
    print(f"   备份位置:  {backup_dir}")


def main():
    parser = argparse.ArgumentParser(description="文件夹增量备份")
    parser.add_argument("--source", required=True, help="源目录路径")
    parser.add_argument("--target", required=True, help="备份目标目录")
    parser.add_argument("--exclude", nargs="*", default=["node_modules", ".git", "__pycache__", "*.tmp"],
                        help="排除的文件/目录模式")
    parser.add_argument("--max-versions", type=int, default=7, help="保留的备份版本数（默认7）")
    args = parser.parse_args()

    backup(args.source, args.target, args.exclude or [], args.max_versions)


if __name__ == "__main__":
    main()
