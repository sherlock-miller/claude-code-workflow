#!/usr/bin/env python3
"""PDF 文本提取工具。"""

import argparse
import os
import sys


def check_deps():
    for lib in ("pdfplumber", "PyPDF2", "pikepdf"):
        try:
            __import__(lib.replace("-", "_"))
            print(f"✓ 使用 {lib}")
            return lib
        except ImportError:
            continue
    print("缺少 PDF 处理库。请安装以下之一：")
    print("  pip install pdfplumber   (推荐，文本提取质量最好)")
    print("  pip install PyPDF2       (轻量级)")
    sys.exit(1)


def extract_pdf(filepath: str) -> dict:
    """提取单个 PDF 的文本内容。"""
    result = {"file": filepath, "pages": [], "full_text": "", "error": None}
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    result["pages"].append({"page": i, "text": text.strip()})
            result["full_text"] = "\n\n".join(p["text"] for p in result["pages"])
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            for i, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text:
                    result["pages"].append({"page": i, "text": text.strip()})
            result["full_text"] = "\n\n".join(p["text"] for p in result["pages"])
        except Exception as e:
            result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    return result


def process_directory(directory: str, output_file: str = None, fmt: str = "md"):
    """批量处理目录中的所有 PDF。"""
    pdf_files = [os.path.join(directory, f) for f in os.listdir(directory)
                 if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(directory, f))]

    if not pdf_files:
        print(f"在 '{directory}' 中未找到 PDF 文件")
        return

    print(f"找到 {len(pdf_files)} 个 PDF 文件\n")
    results = []
    for i, fp in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] 处理: {os.path.basename(fp)}")
        r = extract_pdf(fp)
        results.append(r)
        if r["error"]:
            print(f"  ❌ {r['error']}")
        else:
            print(f"  ✅ {len(r['pages'])} 页, {len(r['full_text'])} 字符")

    # 输出
    if fmt == "json":
        import json
        out = json.dumps(results, ensure_ascii=False, indent=2)
    elif fmt == "md":
        lines = ["# PDF 提取结果\n"]
        for r in results:
            fname = os.path.basename(r["file"])
            lines.append(f"## {fname}")
            if r["error"]:
                lines.append(f"❌ 错误: {r['error']}\n")
            else:
                lines.append(f"共 {len(r['pages'])} 页\n")
                lines.append(r["full_text"][:10000])
                lines.append("\n---\n")
        out = "\n".join(lines)
    else:  # txt
        lines = []
        for r in results:
            lines.append(f"=== {os.path.basename(r['file'])} ===")
            if r["error"]:
                lines.append(f"[错误: {r['error']}]")
            else:
                lines.append(r["full_text"])
            lines.append("")
        out = "\n".join(lines)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"\n📄 结果已保存到: {output_file}")
    else:
        print(out)


def main():
    parser = argparse.ArgumentParser(description="PDF 文本提取")
    parser.add_argument("path", help="PDF 文件路径或包含 PDF 的目录路径")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--format", choices=["txt", "md", "json"], default="md", help="输出格式")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"错误：路径 '{args.path}' 不存在")
        sys.exit(1)

    if os.path.isdir(args.path):
        process_directory(args.path, args.output, args.format)
    else:
        r = extract_pdf(args.path)
        if r["error"]:
            print(f"提取失败: {r['error']}")
        else:
            print(r["full_text"])


if __name__ == "__main__":
    main()
