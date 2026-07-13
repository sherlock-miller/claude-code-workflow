#!/usr/bin/env python3
"""批量网页抓取工具。"""

import argparse
import json
import sys


def check_deps():
    missing = []
    for mod in ("requests", "bs4"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"缺少依赖：{', '.join(missing)}")
        print(f"请运行: pip install {' '.join(missing)}")
        sys.exit(1)


def scrape_urls(urls: list, output_format: str = "json", output_file: str = None):
    """抓取多个 URL 并提取关键信息。"""
    check_deps()
    import requests
    from bs4 import BeautifulSoup

    results = []
    for i, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue
        print(f"[{i}/{len(urls)}] 抓取: {url}")
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 提取基本信息
            title = soup.title.string.strip() if soup.title else ""
            # 移除 script/style 后取正文
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            body_text = soup.body.get_text(separator="\n", strip=True) if soup.body else ""
            # 截取前 5000 字符
            body_text = body_text[:5000]

            results.append({
                "url": url,
                "title": title,
                "status_code": resp.status_code,
                "content_preview": body_text,
            })
            print(f"  ✅ 成功: {len(body_text)} 字符")
        except Exception as e:
            results.append({"url": url, "error": str(e)})
            print(f"  ❌ 失败: {e}")

    # 输出
    if output_format == "json":
        out = json.dumps(results, ensure_ascii=False, indent=2)
    elif output_format == "csv":
        import csv
        import io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["url", "title", "status_code", "content_preview", "error"])
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
        out = buf.getvalue()
    elif output_format == "md":
        lines = ["# 网页抓取结果\n"]
        for r in results:
            if "error" in r:
                lines.append(f"- **{r['url']}**: ❌ {r['error']}")
            else:
                lines.append(f"## {r['title']}")
                lines.append(f"- URL: {r['url']}")
                lines.append(f"- 状态码: {r['status_code']}")
                lines.append(f"\n{r['content_preview'][:1000]}\n")
        out = "\n".join(lines)
    else:
        out = json.dumps(results, ensure_ascii=False, indent=2)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"\n📄 结果已保存到: {output_file}")
    else:
        print(out)

    return results


def main():
    parser = argparse.ArgumentParser(description="批量网页抓取")
    parser.add_argument("--urls", help="URL 列表文件（每行一个）")
    parser.add_argument("--url", action="append", dest="url_list", help="直接指定 URL（可重复使用）")
    parser.add_argument("--format", choices=["json", "csv", "md"], default="json", help="输出格式")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    urls = []
    if args.urls:
        with open(args.urls, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    if args.url_list:
        urls.extend(args.url_list)
    if not urls:
        print("请通过 --urls 或 --url 指定要抓取的 URL")
        sys.exit(1)

    scrape_urls(urls, args.format, args.output)


if __name__ == "__main__":
    main()
