#!/usr/bin/env python3
"""批量数据报告生成器。"""

import argparse
import json
import os
import sys
from datetime import datetime


TEMPLATES = {
    "summary": """# {title}

生成时间: {date}

## 数据概览

{overview}

## 详细内容

{details}
""",
    "table": """# {title}

| 序号 | 来源 | 标题 | 备注 |
|------|------|------|------|
{table_rows}

> 生成时间: {date}
""",
}


def load_input(input_file: str) -> list:
    """加载输入数据（JSON 或 CSV）。"""
    if input_file.endswith(".json"):
        with open(input_file, "r", encoding="utf-8") as f:
            return json.load(f)
    elif input_file.endswith(".csv"):
        import csv
        rows = []
        with open(input_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        return rows
    elif input_file.endswith(".md"):
        with open(input_file, "r", encoding="utf-8") as f:
            return [{"content": f.read(), "source": input_file}]
    else:
        # 尝试作为纯文本
        with open(input_file, "r", encoding="utf-8") as f:
            return [{"content": f.read(), "source": input_file}]


def generate_report(data: list, template_name: str, title: str) -> str:
    """根据模板生成报告。"""
    date = datetime.now().strftime("%Y-%m-%d %H:%M")

    if template_name == "summary":
        overview_items = []
        details_items = []
        for i, item in enumerate(data, 1):
            src = item.get("source", item.get("url", item.get("file", f"条目{i}")))
            overview_items.append(f"- **来源 {i}**: {src}")
            if "title" in item:
                details_items.append(f"### {item['title']}")
            if "content" in item:
                details_items.append(item["content"][:2000])
            elif "content_preview" in item:
                details_items.append(item["content_preview"][:2000])
            elif "full_text" in item:
                details_items.append(item["full_text"][:2000])
        return TEMPLATES["summary"].format(
            title=title,
            date=date,
            overview="\n".join(overview_items),
            details="\n\n".join(details_items) if details_items else "（无详细内容）",
        )

    elif template_name == "table":
        rows = []
        for i, item in enumerate(data, 1):
            src = item.get("source", item.get("url", item.get("file", f"条目{i}"))
            title_val = item.get("title", item.get("source", "-"))
            note = item.get("error", item.get("status_code", "-"))
            rows.append(f"| {i} | {src[:50]} | {str(title_val)[:40]} | {str(note)[:30]} |")
        return TEMPLATES["table"].format(
            title=title,
            date=date,
            table_rows="\n".join(rows),
        )

    return ""


def main():
    parser = argparse.ArgumentParser(description="报告生成器")
    parser.add_argument("--input", required=True, help="输入数据文件（JSON/CSV/MD）")
    parser.add_argument("--template", choices=["summary", "table"], default="summary", help="报告模板")
    parser.add_argument("--title", default="处理报告", help="报告标题")
    parser.add_argument("--output", default="report.md", help="输出文件路径")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误：输入文件 '{args.input}' 不存在")
        sys.exit(1)

    data = load_input(args.input)
    if not data:
        print("输入数据为空")
        return

    report = generate_report(data, args.template, args.title)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 报告已生成: {args.output}")


if __name__ == "__main__":
    main()
