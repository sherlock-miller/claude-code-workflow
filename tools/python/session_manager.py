"""Claude Code 会话管理器 — 查看、搜索、归档、重命名对话记录."""
import io
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECTS_DIR = Path.home() / ".claude" / "projects"
ARCHIVE_DIR = Path.home() / ".claude" / "archived_sessions"


def extract_session_info(jsonl_path: Path) -> dict | None:
    """从 JSONL 文件中提取会话摘要信息."""
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            first_user_msg = ""
            title = ""
            timestamp = ""
            line_count = 0
            for line in f:
                line_count += 1
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = entry.get("type", "")
                if t == "ai-title":
                    title = entry.get("aiTitle", "")
                if not first_user_msg and t == "user":
                    msg = entry.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        first_user_msg = content[:120]
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                first_user_msg = part["text"][:120]
                                break
                if not timestamp and entry.get("timestamp"):
                    timestamp = entry["timestamp"]
        if not first_user_msg and not title:
            return None
        return {
            "uuid": jsonl_path.stem,
            "name": title,
            "preview": first_user_msg,
            "date": timestamp[:19] if timestamp else "未知",
            "messages": line_count,
            "size_kb": round(jsonl_path.stat().st_size / 1024, 1),
        }
    except Exception:
        return None


def list_sessions(project: str | None = None) -> list[dict]:
    """列出所有项目或指定项目的会话."""
    sessions = []
    projects = [PROJECTS_DIR / project] if project else sorted(PROJECTS_DIR.iterdir())
    for proj_dir in projects:
        if not proj_dir.is_dir() or proj_dir.name == "MEMORY.md":
            continue
        for f in sorted(proj_dir.iterdir()):
            if not f.suffix == ".jsonl":
                continue
            info = extract_session_info(f)
            if info:
                info["project"] = proj_dir.name
                sessions.append(info)
    sessions.sort(key=lambda s: s["date"], reverse=True)
    return sessions


def print_table(sessions: list[dict]):
    """打印会话列表表格."""
    if not sessions:
        print("没有找到会话记录。")
        return
    print(f"\n{'#':<4} {'日期':<20} {'名称/预览':<55} {'消息':<6} {'大小':<8} {'项目':<25}")
    print("-" * 125)
    for i, s in enumerate(sessions, 1):
        label = s["name"] if s["name"] else s["preview"]
        if len(label) > 52:
            label = label[:49] + "..."
        print(f"{i:<4} {s['date']:<20} {label:<55} {s['messages']:<6} {s['size_kb']:<6}KB {s['project']:<25}")
    print(f"\n共 {len(sessions)} 个会话")


def archive_sessions(sessions: list[dict], indices: list[int]):
    """归档指定序号的会话."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for idx in indices:
        if idx < 1 or idx > len(sessions):
            print(f"序号 {idx} 无效，跳过")
            continue
        s = sessions[idx - 1]
        proj_dir = PROJECTS_DIR / s["project"]
        jsonl_file = proj_dir / f"{s['uuid']}.jsonl"
        sub_dir = proj_dir / s["uuid"]

        if not jsonl_file.exists():
            print(f"文件不存在: {jsonl_file}")
            continue

        dest_file = ARCHIVE_DIR / jsonl_file.name
        shutil.move(str(jsonl_file), str(dest_file))
        print(f"已归档: {s['uuid']}")

        if sub_dir.exists():
            dest_sub = ARCHIVE_DIR / sub_dir.name
            shutil.move(str(sub_dir), str(dest_sub))
            print(f"  子目录已归档: {s['uuid']}")


def unarchive_sessions(uuids: list[str]):
    """从归档恢复会话."""
    if not ARCHIVE_DIR.exists():
        print("归档目录不存在。")
        return
    for uuid in uuids:
        jsonl_file = ARCHIVE_DIR / f"{uuid}.jsonl"
        if not jsonl_file.exists():
            print(f"归档中未找到: {uuid}")
            continue
        info = extract_session_info(jsonl_file)
        if not info:
            print(f"无法读取: {uuid}")
            continue
        project = info.get("project", "")
        if not project:
            print(f"无法确定项目: {uuid}")
            continue
        dest_dir = PROJECTS_DIR / project
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(jsonl_file), str(dest_dir / jsonl_file.name))
        print(f"已恢复: {uuid} → {project}")
        sub_dir = ARCHIVE_DIR / uuid
        if sub_dir.exists():
            shutil.move(str(sub_dir), str(dest_dir / uuid))


def rename_session(sessions: list[dict], index: int, new_name: str):
    """重命名指定序号的会话 — 追加 ai-title 条目到 JSONL."""
    if index < 1 or index > len(sessions):
        print(f"序号 {index} 无效")
        return
    s = sessions[index - 1]
    proj_dir = PROJECTS_DIR / s["project"]
    jsonl_file = proj_dir / f"{s['uuid']}.jsonl"

    if not jsonl_file.exists():
        # 检查归档
        jsonl_file = ARCHIVE_DIR / f"{s['uuid']}.jsonl"
        if not jsonl_file.exists():
            print(f"文件不存在: {s['uuid']}")
            return

    entry = {
        "type": "ai-title",
        "aiTitle": new_name,
        "sessionId": s["uuid"],
    }
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"已重命名: {s['uuid'][:8]}... → {new_name}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python session_manager.py list [项目名]       — 列出所有会话")
        print("  python session_manager.py search <关键词>      — 搜索会话")
        print("  python session_manager.py archive <序号> [...]  — 归档指定会话")
        print("  python session_manager.py unarchive <uuid> [...]— 恢复归档")
        print("  python session_manager.py rename <序号> <新名称>— 重命名会话")
        return

    cmd = sys.argv[1]

    if cmd == "list":
        project = sys.argv[2] if len(sys.argv) > 2 else None
        sessions = list_sessions(project)
        print_table(sessions)

    elif cmd == "search":
        keyword = sys.argv[2]
        all_sessions = list_sessions()
        matched = [s for s in all_sessions
                   if keyword.lower() in (s["name"] + s["preview"]).lower()]
        print_table(matched)

    elif cmd == "archive":
        sessions = list_sessions()
        print_table(sessions)
        indices = [int(a) for a in sys.argv[2:]]
        print(f"\n归档 {len(indices)} 个会话...")
        archive_sessions(sessions, indices)
        print("完成。")

    elif cmd == "unarchive":
        uuids = sys.argv[2:]
        unarchive_sessions(uuids)

    elif cmd == "rename":
        index = int(sys.argv[2])
        new_name = " ".join(sys.argv[3:])
        sessions = list_sessions()
        rename_session(sessions, index, new_name)

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
