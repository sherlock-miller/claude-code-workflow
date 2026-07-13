#!/usr/bin/env python3
"""
剪贴板截图识别工具 — Clipboard Vision
======================================
读取 Windows 剪贴板中的截图，发送给豆包视觉模型识别，返回文本描述。

用法:
    python clipboard_vision.py                  # 识别剪贴板图片
    python clipboard_vision.py -p "翻译这段文字"  # 带自定义提示词
    python clipboard_vision.py -o result.txt    # 输出到文件

工作流程:
    1. Win+Shift+S 截图 (图片进入剪贴板)
    2. 告诉 Claude "识别剪贴板" 或 "看截图"
    3. Claude 运行此脚本，获取识别结果

依赖:
    pip install Pillow requests
"""

import os
import sys
import io
import base64
import argparse
import tempfile
from pathlib import Path

# ============================================================
# 配置
# ============================================================
ARK_API_KEY = os.environ.get(
    "ARK_API_KEY",
    "ark-a73d32ae-9cae-42a7-97bc-d5700f069306-e5ac6"
)
ARK_MODEL = os.environ.get("ARK_MODEL", "ep-20260528213610-cl26k")  # Doubao-Seed-2.0-lite
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})


def get_clipboard_image():
    """从 Windows 剪贴板读取图片.

    支持三种来源:
      1. Win+Shift+S 截图 → 图片像素数据
      2. Ctrl+C 复制图片文件 → 文件路径列表
      3. 浏览器右键"复制图片" → 图片像素数据

    返回 (PIL.Image, 来源描述) 或 (None, 错误信息).
    """
    from PIL import Image, ImageGrab

    data = ImageGrab.grabclipboard()

    if data is None:
        return None, "剪贴板为空"

    # 情况1: 图片像素数据 (截图/复制图片)
    if hasattr(data, "size"):
        return data, f"截图 ({data.size[0]}x{data.size[1]})"

    # 情况2: 文件路径列表 (在资源管理器中 Ctrl+C 复制文件)
    if isinstance(data, list):
        image_files = [f for f in data if Path(str(f)).suffix.lower() in IMAGE_EXTS]
        if not image_files:
            return None, f"剪贴板中有 {len(data)} 个文件，但没有图片格式"
        filepath = str(image_files[0])
        if not os.path.exists(filepath):
            return None, f"文件不存在: {filepath}"
        try:
            img = Image.open(filepath)
            return img, f"文件 ({Path(filepath).name}, {img.size[0]}x{img.size[1]})"
        except Exception as e:
            return None, f"无法打开图片文件: {e}"

    # 情况3: 单文件路径字符串
    if isinstance(data, str):
        filepath = data
        if not os.path.exists(filepath):
            return None, f"文件不存在: {filepath}"
        ext = Path(filepath).suffix.lower()
        if ext not in IMAGE_EXTS:
            return None, f"文件不是图片格式: {ext}"
        try:
            img = Image.open(filepath)
            return img, f"文件 ({Path(filepath).name}, {img.size[0]}x{img.size[1]})"
        except Exception as e:
            return None, f"无法打开图片文件: {e}"

    return None, f"不支持的剪贴板数据类型: {type(data).__name__}"


def image_to_base64_uri(img) -> str:
    """PIL Image → base64 data URI."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def call_vision_api(image_uri: str, prompt: str, max_tokens: int = 4096) -> str:
    """调用豆包视觉 API."""
    import requests

    payload = {
        "model": ARK_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_uri, "detail": "high"}},
                {"type": "text", "text": prompt},
            ]
        }],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "thinking": {"type": "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {ARK_API_KEY}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"API 返回 {resp.status_code}: {resp.text[:500]}")

    return resp.json()["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser(
        description="剪贴板截图识别 — 读取 Windows 剪贴板图片并发送给豆包视觉模型"
    )
    parser.add_argument(
        "-p", "--prompt",
        default=(
            "请详细描述这张截图的内容。包括："
            "所有文字（保留原文）、界面元素、图表、代码、公式（LaTeX格式）、"
            "以及任何其他可见信息。不要遗漏任何细节。"
        ),
        help="自定义提示词"
    )
    parser.add_argument("-o", "--output", help="将结果写入文件")
    parser.add_argument("-s", "--save", help="将剪贴板图片保存到指定路径（同时识别）")
    parser.add_argument("--save-only", help="仅保存剪贴板图片，不识别")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    log = print if args.verbose else lambda *a, **kw: None

    # 读取剪贴板
    log("[INFO] 读取剪贴板...")
    img, source = get_clipboard_image()

    if img is None:
        print(f"[ERROR] {source}", file=sys.stderr)
        sys.exit(1)

    log(f"[INFO] 来源: {source}")

    # 仅保存模式
    if args.save_only:
        img.save(args.save_only)
        print(f"[INFO] 图片已保存: {args.save_only}", file=sys.stderr)
        return

    # 保存（如果指定）
    if args.save:
        img.save(args.save)
        log(f"[INFO] 图片已保存: {args.save}")

    # 编码并调用 API
    log("[INFO] 编码图片...")
    image_uri = image_to_base64_uri(img)
    log(f"[INFO] base64 编码完成 ({len(image_uri):,} 字符)")

    log("[INFO] 调用豆包视觉 API...")
    try:
        result = call_vision_api(image_uri, args.prompt)
    except Exception as e:
        print(f"[ERROR] API 调用失败: {e}", file=sys.stderr)
        sys.exit(2)

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[INFO] 结果已写入: {args.output}", file=sys.stderr)
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(result)


if __name__ == "__main__":
    main()
