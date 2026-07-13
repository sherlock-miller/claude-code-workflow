"""
Claude Code 会话提问索引 — 从 JSONL 提取用户提问，生成可检索的提问目录
用法:
  python session_questions.py                     # 当前项目最近会话
  python session_questions.py --all               # 当前项目所有会话
  python session_questions.py --search "关键词"    # 搜索所有会话
  python session_questions.py --id <session-uuid>  # 指定会话
"""

import sys, os, json, glob, io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = os.path.expanduser("~/.claude/projects/E--claude-code")


def find_sessions():
    return sorted(glob.glob(os.path.join(BASE, "*.jsonl")), key=os.path.getmtime, reverse=True)


def extract_questions(jsonl_path):
    """从一个 JSONL 文件中提取用户提问"""
    questions = []
    session_id = os.path.basename(jsonl_path).replace(".jsonl", "")
    mtime = datetime.fromtimestamp(os.path.getmtime(jsonl_path))

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # Claude Code JSONL 格式：entry_type 或 type
                etype = data.get('entry_type') or data.get('type', '')
                if etype == 'user' or (isinstance(data.get('message'), dict) and data['message'].get('role') == 'user'):
                    content = data.get('message', {}).get('content', '')
                    if isinstance(content, list):
                        text = ' '.join(
                            c.get('text', '') if isinstance(c, dict) else str(c)
                            for c in content
                        )
                    elif isinstance(content, str):
                        text = content
                    else:
                        text = str(data.get('message', ''))

                    if text.strip():
                        questions.append({
                            'text': text[:200].replace('\n', ' '),
                            'full': text,
                            'timestamp': data.get('timestamp', ''),
                            'uuid': data.get('uuid', ''),
                            'line': len(questions),
                        })
            except (json.JSONDecodeError, KeyError):
                pass

    return session_id, mtime, questions


def main():
    import argparse
    p = argparse.ArgumentParser(description='Claude Code 会话提问索引')
    p.add_argument('--all', action='store_true', help='当前项目所有会话')
    p.add_argument('--search', type=str, help='搜索关键词')
    p.add_argument('--id', type=str, help='指定会话 UUID')
    p.add_argument('--latest', type=int, default=5, help='最近 N 个会话 (默认 5)')
    p.add_argument('--export', action='store_true', help='导出为 Markdown 文件')
    args = p.parse_args()

    sessions = find_sessions()

    if args.id:
        sessions = [s for s in sessions if args.id in s]

    limit = None if args.all else args.latest
    sessions = sessions[:limit]

    output_lines = []
    total_questions = 0

    for i, sp in enumerate(sessions):
        sid, mtime, questions = extract_questions(sp)
        if args.search:
            questions = [q for q in questions if args.search.lower() in q['text'].lower()]
        if not questions:
            continue

        time_str = mtime.strftime('%m-%d %H:%M')
        session_short = sid[:8]
        header = f"\n## 会话 {i+1} [{session_short}...] — {time_str} ({len(questions)} 条提问)\n"
        output_lines.append(header)
        print(header)

        for j, q in enumerate(questions):
            line = f"{j+1}. {q['text']}"
            output_lines.append(line)
            print(line)
            total_questions += 1

    session_count = len(sessions)
    label = "匹配" if args.search else ""
    print(f"\n---\n共 {session_count} 个{label}会话, {total_questions} 条提问")

    if args.export:
        md_path = os.path.expanduser("~/.claude/session_questions.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Claude Code 提问索引\n> 生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write('\n'.join(output_lines))
        print(f"\n已导出: {md_path}")


if __name__ == "__main__":
    main()
