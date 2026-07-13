#!/usr/bin/env python3
"""
知识库检索系统 — Knowledge Base & RAG
======================================
将预处理后的 Markdown 课件构建为可检索的知识库。

功能:
  1. build  — 将 Markdown 文件分块、嵌入、存入 Chroma 向量数据库
  2. search — 根据问题检索最相关的文本块
  3. info   — 查看知识库状态

用法:
  python knowledge_base.py build <md目录>   [-n 知识库名称] [-v]
  python knowledge_base.py search <问题>    [-n 知识库名称] [-k 返回条数]
  python knowledge_base.py info             [-n 知识库名称]

示例:
  python knowledge_base.py build ./course_md/ -n 工程数值方法 -v
  python knowledge_base.py search "有限元方法的基本原理" -n 工程数值方法 -k 5
"""

import os
import sys
import json
import argparse
from pathlib import Path

# ============================================================
# 配置
# ============================================================
DEFAULT_DB_DIR = os.path.join(os.path.expanduser("~"), ".claude", "knowledge_bases")
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # 多语言小模型, 384维


def get_db_path(name: str) -> str:
    return os.path.join(DEFAULT_DB_DIR, name)


# ============================================================
# Chunking
# ============================================================

def split_markdown(text: str, source_name: str = "",
                   max_chunk_size: int = 800, overlap: int = 100) -> list:
    """将 Markdown 文本按语义分块.

    策略:
      1. 优先按 ## 标题分割
      2. 如果单个 section 太长，按段落再切
      3. 每个 chunk 保留来源信息
    """
    lines = text.split("\n")
    chunks = []
    current_title = source_name
    current_lines = []
    current_len = 0

    def flush_chunk():
        nonlocal current_lines, current_len
        if not current_lines:
            return
        content = "\n".join(current_lines).strip()
        if len(content) < 20:  # 跳过太短的
            current_lines = []
            current_len = 0
            return
        chunks.append({
            "content": content,
            "source": source_name,
            "section": current_title,
            "char_count": len(content),
        })
        current_lines = []
        current_len = 0

    for line in lines:
        stripped = line.strip()
        line_len = len(stripped)

        # 遇到新标题 → 提交前一个块
        if stripped.startswith("## "):
            flush_chunk()
            current_title = stripped.lstrip("# ").strip()
            current_lines.append(line)
            current_len += line_len
        elif stripped.startswith("# "):
            flush_chunk()
            current_title = stripped.lstrip("# ").strip()
            current_lines.append(line)
            current_len += line_len
        elif stripped == "" and current_len > max_chunk_size * 0.7:
            # 段落空行 + 接近上限 → 提交
            flush_chunk()
        else:
            current_lines.append(line)
            current_len += line_len

        # 超长保护
        if current_len > max_chunk_size + overlap:
            flush_chunk()

    flush_chunk()

    # 添加重叠：每个chunk末尾加上下一个chunk开头的一小段
    for i in range(len(chunks) - 1):
        overlap_text = chunks[i + 1]["content"][:overlap]
        if overlap_text:
            chunks[i]["content"] += "\n\n...\n\n" + overlap_text

    return chunks


# ============================================================
# 嵌入模型
# ============================================================

class Embedder:
    """文本嵌入器（惰性加载）."""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        return self._model

    def encode(self, texts: list) -> list:
        return self.model.encode(texts, show_progress_bar=False).tolist()


_embedder = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


# ============================================================
# 构建知识库
# ============================================================

def cmd_build(args):
    """构建知识库: 读取MD → 分块 → 嵌入 → 存入Chroma."""
    import chromadb
    from chromadb.config import Settings

    md_dir = os.path.abspath(args.md_dir)
    if not os.path.isdir(md_dir):
        print(f"[ERROR] 目录不存在: {md_dir}", file=sys.stderr)
        sys.exit(1)

    db_path = get_db_path(args.name)
    os.makedirs(db_path, exist_ok=True)

    print(f"[INFO] 知识库名称: {args.name}")
    print(f"[INFO] 存储位置: {db_path}")

    # 读取所有 Markdown 文件
    md_files = list(Path(md_dir).glob("*.md"))
    if not md_files:
        print(f"[ERROR] 目录中没有 .md 文件: {md_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 找到 {len(md_files)} 个 Markdown 文件")

    # 分块
    all_chunks = []
    for md_file in md_files:
        if md_file.name.startswith("."):
            continue
        with open(md_file, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = split_markdown(text, source_name=md_file.stem)
        all_chunks.extend(chunks)
        if args.verbose:
            print(f"  {md_file.name}: {len(chunks)} 块")

    print(f"[INFO] 总计 {len(all_chunks)} 个文本块")
    if not all_chunks:
        print("[ERROR] 没有可用的文本块", file=sys.stderr)
        sys.exit(1)

    # 嵌入
    print(f"[INFO] 生成嵌入向量 (模型: {EMBEDDING_MODEL})...")
    embedder = get_embedder()
    texts = [c["content"] for c in all_chunks]
    embeddings = embedder.encode(texts)
    print(f"[INFO] 嵌入完成: {len(embeddings)} 个向量 x {len(embeddings[0])} 维")

    # 存入 Chroma
    print("[INFO] 写入 Chroma 数据库...")
    client = chromadb.PersistentClient(path=db_path, settings=Settings(anonymized_telemetry=False))

    # 删除旧 collection（如果存在）
    try:
        client.delete_collection(args.name)
    except Exception:
        pass

    collection = client.create_collection(
        name=args.name,
        metadata={"description": f"知识库: {args.name}", "chunk_count": len(all_chunks)},
    )

    # 分批写入（Chroma 批量上限）
    batch_size = 500
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        collection.add(
            ids=[f"chunk_{j}" for j in range(i, i + len(batch))],
            documents=[c["content"] for c in batch],
            embeddings=embeddings[i:i + batch_size],
            metadatas=[{"source": c["source"], "section": c["section"]} for c in batch],
        )
        if args.verbose:
            print(f"  写入 {i + len(batch)}/{len(all_chunks)}")

    print(f"[DONE] 知识库 '{args.name}' 构建完成: {len(all_chunks)} 个文本块")


# ============================================================
# 检索查询
# ============================================================

def cmd_search(args):
    """检索知识库."""
    import chromadb
    from chromadb.config import Settings

    db_path = get_db_path(args.name)
    if not os.path.exists(db_path):
        print(f"[ERROR] 知识库不存在: {args.name} (路径: {db_path})", file=sys.stderr)
        print("[INFO] 先用 build 命令构建知识库", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(path=db_path, settings=Settings(anonymized_telemetry=False))

    try:
        collection = client.get_collection(args.name)
    except Exception:
        print(f"[ERROR] 知识库 '{args.name}' 中没有数据", file=sys.stderr)
        sys.exit(1)

    # 嵌入查询
    embedder = get_embedder()
    query_embedding = embedder.encode([args.query])[0]

    # 检索
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=args.k,
        include=["documents", "metadatas", "distances"],
    )

    # 输出
    if args.format == "json":
        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "rank": i + 1,
                "distance": results["distances"][0][i],
                "source": results["metadatas"][0][i].get("source", ""),
                "section": results["metadatas"][0][i].get("section", ""),
                "content": results["documents"][0][i],
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            doc = results["documents"][0][i]
            dist = results["distances"][0][i]
            print(f"\n{'─'*60}")
            print(f"[{i+1}] 来源: {meta.get('source', '?')} | "
                  f"章节: {meta.get('section', '?')} | 距离: {dist:.3f}")
            print(f"{'─'*60}")
            # 截断过长内容
            if len(doc) > 1200:
                print(doc[:1200] + "\n... (已截断)")
            else:
                print(doc)


def cmd_info(args):
    """查看知识库信息."""
    import chromadb
    from chromadb.config import Settings

    db_path = get_db_path(args.name)
    if not os.path.exists(db_path):
        print(f"[ERROR] 知识库不存在: {args.name}", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(path=db_path, settings=Settings(anonymized_telemetry=False))
    try:
        collection = client.get_collection(args.name)
        count = collection.count()
        metadata = collection.metadata or {}
        print(f"知识库: {args.name}")
        print(f"文本块数: {count}")
        print(f"描述: {metadata.get('description', 'N/A')}")
        print(f"存储路径: {db_path}")
    except Exception:
        print(f"[ERROR] 知识库 '{args.name}' 中无数据", file=sys.stderr)
        sys.exit(1)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="知识库检索系统 — Markdown → Chunks → Embeddings → Chroma → RAG"
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # build
    p_build = sub.add_parser("build", help="构建知识库")
    p_build.add_argument("md_dir", help="Markdown 文件目录")
    p_build.add_argument("-n", "--name", default="default", help="知识库名称")
    p_build.add_argument("-v", "--verbose", action="store_true")

    # search
    p_search = sub.add_parser("search", help="检索知识库")
    p_search.add_argument("query", help="查询文本")
    p_search.add_argument("-n", "--name", default="default", help="知识库名称")
    p_search.add_argument("-k", type=int, default=5, help="返回结果数 (默认5)")
    p_search.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")

    # info
    p_info = sub.add_parser("info", help="查看知识库状态")
    p_info.add_argument("-n", "--name", default="default", help="知识库名称")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "info":
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
