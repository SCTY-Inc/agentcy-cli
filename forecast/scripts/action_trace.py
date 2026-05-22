import json
import os
import sqlite3
from typing import Any, Dict, List, Tuple

FILTERED_ACTIONS = {"refresh", "sign_up"}
ACTION_TYPE_MAP = {
    "create_post": "CREATE_POST",
    "like_post": "LIKE_POST",
    "dislike_post": "DISLIKE_POST",
    "repost": "REPOST",
    "quote_post": "QUOTE_POST",
    "follow": "FOLLOW",
    "mute": "MUTE",
    "create_comment": "CREATE_COMMENT",
    "like_comment": "LIKE_COMMENT",
    "dislike_comment": "DISLIKE_COMMENT",
    "search_posts": "SEARCH_POSTS",
    "search_user": "SEARCH_USER",
    "trend": "TREND",
    "do_nothing": "DO_NOTHING",
    "interview": "INTERVIEW",
}


def get_agent_names_from_config(config: Dict[str, Any]) -> Dict[int, str]:
    agent_names: Dict[int, str] = {}
    for agent_config in config.get("agent_configs", []):
        agent_id = agent_config.get("agent_id")
        if agent_id is None:
            continue
        agent_names[int(agent_id)] = agent_config.get("entity_name", f"Agent_{agent_id}")
    return agent_names


def fetch_new_actions_from_db(
    db_path: str,
    last_rowid: int,
    agent_names: Dict[int, str],
) -> Tuple[List[Dict[str, Any]], int]:
    actions: List[Dict[str, Any]] = []
    new_last_rowid = last_rowid
    if not os.path.exists(db_path):
        return actions, new_last_rowid

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT rowid, user_id, action, info
            FROM trace
            WHERE rowid > ?
            ORDER BY rowid ASC
            """,
            (last_rowid,),
        )
        for rowid, user_id, action, info_json in cursor.fetchall():
            new_last_rowid = rowid
            if action in FILTERED_ACTIONS:
                continue
            try:
                action_args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                action_args = {}
            simplified_args = {}
            for key in (
                "content",
                "post_id",
                "comment_id",
                "quoted_id",
                "new_post_id",
                "follow_id",
                "query",
                "like_id",
                "dislike_id",
            ):
                if key in action_args:
                    simplified_args[key] = action_args[key]
            actions.append(
                {
                    "agent_id": int(user_id),
                    "agent_name": agent_names.get(int(user_id), f"Agent_{user_id}"),
                    "action_type": ACTION_TYPE_MAP.get(action, str(action).upper()),
                    "action_args": simplified_args,
                }
            )
        conn.close()
    except Exception as exc:  # pragma: no cover - best-effort logging path
        print(f"Failed to read actions from database: {exc}")

    return actions, new_last_rowid
