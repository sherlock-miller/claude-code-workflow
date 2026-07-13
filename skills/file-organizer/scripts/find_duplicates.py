#!/usr/bin/env python3
"""查找目录中的重复文件（基于 SHA256 哈希）。"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict
from typing import Dict, List


def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def hash_file(filepath: str, chunk_size: int = 8192) -> str:
    """计算文件的 SHA256 哈希。"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, IOError) as e:
        print(f"⚠ 无法读取: {filepath} ({e})")
        return ""


def find_duplicates(path: str, delete_after: bool = False) -> Dict[str, List[str]]:
    """扫描目录查找重复文件。先按大小预筛选，再哈希比对。"""
    if not os.path.isdir(path):
        print(f"错误：目录 '{path}' 不存在")
        sys.exit(1)

    # 第一阶段：按大小分组
    size_map: Dict[int, List[str]] = defaultdict(list)
    total_files = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.startswith("."):
                continue
            fp = os.path.join(root, f)
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue
            if size > 0:  # 跳过空文件
                size_map[size].append(fp)
            total_files += 1

    # 第二阶段：对相同大小的文件进行哈希比对
    duplicates: Dict[str, List[str]] = defaultdict(list)
    potential_dup_groups = [files for files in size_map.values() if len(files) > 1]

    for group in potential_dup_groups:
        hashes: Dict[str, str] = {}  # hash -> first file path
        for fp in group:
            h = hash_file(fp)
            if not h:
                continue
            if h in hashes:
                if h not in duplicates:
                    duplicates[h] = [hashes[h]]
                duplicates[h].append(fp)
            else:
                hashes[h] = fp

    # 输出结果
    if not duplicates:
        print(f"\n扫描了 {total_files} 个文件，未发现重复。")
        return {}

    total_wasted = 0
    dup_count = 0
    print(f"\n🔍 扫描了 {total_files} 个文件，发现 {len(duplicates)} 组重复：\n")

    for i, (h, files) in enumerate(duplicates.items(), 1):
        size = os.path.getsize(files[0])
        wasted = size * (len(files) - 1)
        total_wasted += wasted
        dup_count += len(files) - 1
        print(f"--- 重复组 {i} ({format_size(size)} × {len(files)}) ---")
        print(f"  保留: {files[0]}")
        for f in files[1:]:
            print(f"  重复: {f}")
        print()

    print(f"💾 可释放空间: {format_size(total_wasted)} (删除 {dup_count} 个重复文件)")

    if delete_after:
        print("\n⚠ 删除模式已启用，正在删除重复文件...")
        for h, files in duplicates.items():
            for f in files[1:]:
                try:
                    os.remove(f)
                    print(f"  已删除: {f}")
                except OSError as e:
                    print(f"  删除失败: {f} ({e})")
        print("✅ 删除完成。")

    return duplicates


def main():
    parser = argparse.ArgumentParser(description="查找重复文件")
    parser.add_argument("path", help="要扫描的目录路径")
    parser.add_argument("--delete", action="store_true", help="自动删除重复文件（保留每组第一个）")
    args = parser.parse_args()
    find_duplicates(args.path, args.delete)


if __name__ == "__main__":
    main()
