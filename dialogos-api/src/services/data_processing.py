from src.config import models_data
from collections import defaultdict
from datetime import datetime
def detect_chat_type(model_name):
    if model_name.startswith("deepseek"):
        return "deepseek"
    return "chatgpt"
def process_messages(messages, chat_type):
    formatted_messages = []
    for msg in messages:
        role = "Human" if msg["role"] == "user" else "Assistant"
        formatted_messages.append(f"{role}: {msg['content']}")
    return "\n".join(formatted_messages)
def validate_message_content(content):
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Message content must be a non-empty string")
    return content.strip()
def analyze_branches(messages):
    chats_with_branches = {}
    for msg in messages:
        chat_name = msg.get("chat_name")
        if not chat_name:
            continue
        if chat_name not in chats_with_branches:
            chats_with_branches[chat_name] = {
                "messages": [],
                "message_ids": set(),
                "parent_children": defaultdict(list),
                "edit_branches": []
            }
        chat_data = chats_with_branches[chat_name]
        msg_id = msg.get("message_id")
        parent_id = msg.get("parent_message_id")
        try:
            timestamp = datetime.fromisoformat(msg.get("timestamp").replace('Z', '+00:00'))
        except (ValueError, TypeError):
            continue
        msg_data = {
            **msg,
            "timestamp_obj": timestamp,
            "children": [],
            "is_branch_point": False
        }
        chat_data["messages"].append(msg_data)
        if msg_id:
            chat_data["message_ids"].add(msg_id)
            if parent_id:
                chat_data["parent_children"][parent_id].append(msg_data)
    for chat_name, chat_data in chats_with_branches.items():
        for parent_id, children in chat_data["parent_children"].items():
            if len(children) > 1:
                children.sort(key=lambda x: x["timestamp_obj"])
                time_gaps = []
                for i in range(1, len(children)):
                    time_diff = (children[i]["timestamp_obj"] - children[i-1]["timestamp_obj"]).total_seconds()
                    time_gaps.append(time_diff)
                for i, gap in enumerate(time_gaps):
                    if gap > 60:
                        branch_data = {
                            "parent_message": parent_id,
                            "original_branch": children[i],
                            "edit_branch": children[i + 1],
                            "time_gap": gap,
                            "branch_messages": []
                        }
                        def collect_branch_messages(msg):
                            branch_data["branch_messages"].append(msg)
                            msg_id = msg.get("message_id")
                            if msg_id in chat_data["parent_children"]:
                                for child in chat_data["parent_children"][msg_id]:
                                    collect_branch_messages(child)
                        collect_branch_messages(children[i + 1])
                        chat_data["edit_branches"].append(branch_data)
    return chats_with_branches