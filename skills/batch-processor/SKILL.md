---
name: batch-processor
description: 批量信息处理 — 从网页、PDF、图片等多源提取信息并生成结构化报告
---

# 批量信息处理

从多种来源批量提取信息，整理为结构化数据或报告。

## 触发条件

- "从这些网页/URL 提取信息"
- "把这个 PDF 的内容提取出来整理成表格"
- "从图片中识别文字"
- "批量处理这些文件并生成报告"
- "爬取这个网站的内容"

## 工作流程

### 1. 网页批量抓取
执行 `scripts/web_scraper.py --urls <urls.txt> --output <输出文件>` 批量抓取网页。
- 支持从文件读取 URL 列表或直接传入
- 提取标题、正文、关键数据
- 输出 JSON/CSV/Markdown

### 2. PDF 文本提取
执行 `scripts/pdf_extractor.py <PDF路径或目录> --output <输出文件>` 提取 PDF 文本。
- 批量处理整个目录的 PDF
- 保留段落结构
- 支持输出 Markdown 或纯文本

### 3. 图片文字识别 (OCR)
当用户需要从图片提取文字时，使用 Python pytesseract 处理。
- 先检查环境是否安装 Tesseract，若未安装则引导用户安装
- 支持批量处理整个目录

### 4. 生成结构化报告
执行 `scripts/generate_report.py --input <数据文件> --template <模板> --output <报告文件>` 
- 将提取的数据整合为统一格式的报告
- 支持 Markdown、HTML 格式

## 依赖
- Python 3.8+
- 网页抓取：`beautifulsoup4`, `requests`
- PDF：`pdfplumber` 或 `PyPDF2`
- OCR：`pytesseract`, `Pillow`（需单独安装 Tesseract 系统包）
- 运行前自动检查依赖，缺失时提示安装命令
