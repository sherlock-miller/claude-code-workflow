#!/usr/bin/env python3
"""文件整理大师 — 主脚本：扫描、分类、重命名、归档。"""

import argparse
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# 文件分类映射
CATEGORIES = {
    "文档": {".doc", ".docx", ".pdf", ".txt", ".md", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".rtf"},
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".psd"},
    "视频": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "代码": {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs", ".sh", ".json", ".xml", ".yaml", ".yml", ".toml"},
}

def get_category(ext: str) -> str:
    for cat, exts in CATEGORIES.items():
        if ext.lower() in exts:
            return cat
    return "其他"

def format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def scan_directory(path: str):
    """扫描目录并按类型分类汇总。"""
    if not os.path.isdir(path):
        print(f"错误：目录 '{path}' 不存在")
        sys.exit(1)

    cat_files = defaultdict(list)
    cat_sizes = defaultdict(int)
    total_size = 0
    total_files = 0

    for root, dirs, files in os.walk(path):
        # 跳过隐藏目录
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.startswith("."):
                continue
            fp = os.path.join(root, f)
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue
            ext = os.path.splitext(f)[1]
            cat = get_category(ext)
            cat_files[cat].append(fp)
            cat_sizes[cat] += size
            total_size += size
            total_files += 1

    print(f"\n📂 扫描目录: {path}")
    print(f"   文件总数: {total_files} | 总大小: {format_size(total_size)}\n")
    print(f"{'类别':<8} {'文件数':<8} {'大小':<12}")
    print("-" * 30)
    for cat in sorted(cat_files.keys()):
        print(f"{cat:<8} {len(cat_files[cat]):<8} {format_size(cat_sizes[cat]):<12}")

    return cat_files

def organize_files(path: str, execute: bool = False):
    """按类别将文件移动到子目录。"""
    cat_files = scan_directory(path)
    if not execute:
        print("\n⚡ 预览模式 — 以下是将要执行的操作（使用 --execute 真正执行）：\n")
    for cat, files in cat_files.items():
        if not files:
            continue
        cat_dir = os.path.join(path, cat)
        for f in files:
            fname = os.path.basename(f)
            dest = os.path.join(cat_dir, fname)
            if f.startswith(cat_dir):
                continue
            print(f"  移动: {fname} → {cat}/")
            if execute:
                os.makedirs(cat_dir, exist_ok=True)
                # 处理重名
                counter = 1
                base, ext = os.path.splitext(dest)
                while os.path.exists(dest):
                    dest = f"{base}_{counter}{ext}"
                    counter += 1
                shutil.move(f, dest)
    if execute:
        print(f"\n✅ 文件整理完成！")
    else:
        print(f"\n提示：加上 --execute 参数来真正执行整理操作。")

def rename_files(path: str, pattern: str, execute: bool = False):
    """批量重命名文件。"""
    if not os.path.isdir(path):
        print(f"错误：目录 '{path}' 不存在")
        sys.exit(1)

    files = sorted([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and not f.startswith(".")])
    if not files:
        print("目录中没有文件")
        return

    print(f"\n🔄 预览重命名（模式: {pattern}）：\n")
    for i, fname in enumerate(files, 1):
        ext = os.path.splitext(fname)[1]
        base = os.path.splitext(fname)[0]
        mod_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(path, fname)))
        new_name = pattern.replace("{date}", mod_time.strftime("%Y%m%d"))
        new_name = new_name.replace("{index}", str(i))
        new_name = new_name.replace("{ext}", ext)
        new_name = new_name.replace("{original}", base)
        if not new_name.endswith(ext):
            new_name += ext
        if fname != new_name:
            print(f"  {fname}  →  {new_name}")
            if execute:
                os.rename(os.path.join(path, fname), os.path.join(path, new_name))
    if not execute:
        print(f"\n提示：加上 --execute 参数来真正执行重命名。")
    else:
        print(f"\n✅ 重命名完成！")

def archive_files(path: str, days: int, execute: bool = False):
    """归档 N 天未修改的文件。"""
    if not os.path.isdir(path):
        print(f"错误：目录 '{path}' 不存在")
        sys.exit(1)

    cutoff = datetime.now() - timedelta(days=days)
    archive_dir = os.path.join(path, f"归档_{cutoff.strftime('%Y%m%d')}")
    archivable = []

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != os.path.basename(archive_dir)]
        for f in files:
            if f.startswith("."):
                continue
            fp = os.path.join(root, f)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
            except OSError:
                continue
            if mtime < cutoff:
                archivable.append(fp)

    print(f"\n📦 发现 {len(archivable)} 个 {days} 天前的文件：\n")
    for f in archivable:
        print(f"  {f}")
    if not execute:
        print(f"\n提示：加上 --execute 参数来真正执行归档。")
    elif archivable:
        os.makedirs(archive_dir, exist_ok=True)
        for f in archivable:
            rel_path = os.path.relpath(f, path)
            dest = os.path.join(archive_dir, rel_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(f, dest)
        print(f"\n✅ 已归档到: {archive_dir}")

def main():
    parser = argparse.ArgumentParser(description="文件整理大师")
    subparsers = parser.add_subparsers(dest="command", help="操作类型")

    # scan
    sp_scan = subparsers.add_parser("scan", help="扫描目录并显示分类汇总")
    sp_scan.add_argument("path", help="要扫描的目录路径")

    # organize
    sp_org = subparsers.add_parser("organize", help="按类型分类整理文件")
    sp_org.add_argument("path", help="要整理的目录路径")
    sp_org.add_argument("--execute", action="store_true", help="真正执行整理操作")

    # rename
    sp_rename = subparsers.add_parser("rename", help="批量重命名文件")
    sp_rename.add_argument("path", help="目标目录路径")
    sp_rename.add_argument("--pattern", default="{original}{ext}", help="重命名模式，可用变量: {date} {index} {ext} {original}")
    sp_rename.add_argument("--execute", action="store_true", help="真正执行重命名操作")

    # archive
    sp_archive = subparsers.add_parser("archive", help="归档旧文件")
    sp_archive.add_argument("path", help="目标目录路径")
    sp_archive.add_argument("--days", type=int, default=90, help="归档多少天前的文件（默认90）")
    sp_archive.add_argument("--execute", action="store_true", help="真正执行归档操作")

    args = parser.parse_args()
    if args.command == "scan":
        scan_directory(args.path)
    elif args.command == "organize":
        organize_files(args.path, args.execute)
    elif args.command == "rename":
        rename_files(args.path, args.pattern, args.execute)
    elif args.command == "archive":
        archive_files(args.path, args.days, args.execute)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
