#!/usr/bin/env python3
"""Model configuration system for lesson AI - supports multiple models with role-based limits.

This module provides:
1. Model registry from config.json
2. Role-based usage limits (student vs teacher)
3. Per-model usage tracking
4. Hot-reload of configuration

Usage:
    from model_config import get_available_models, check_model_usage, record_model_usage

    # Get models for a user
    models = get_available_models(user='student01', lesson='L4-01', role='student')

    # Check if usage allowed
    result = check_model_usage(user='student01', lesson='L4-01', model='deepseek-reasoner', role='student')
    if result['allowed']:
        # Make API call
        record_model_usage(user='student01', lesson='L4-01', model='deepseek-reasoner', tokens={'input': 450, ...})
"""
import json
import os
import time
import datetime
import sqlite3
from typing import Dict, List, Optional, Any, Tuple

# Same paths as lesson_ai.py
CFG_DIR = os.environ.get("LESSON_AI_CFG", "/etc/iits-lesson-ai")
DATA_DIR = os.environ.get("LESSON_AI_DATA", "/var/lib/iits-lesson-ai")
HKT = datetime.timezone(datetime.timedelta(hours=8))

# Cache for config (reloaded every 60 seconds)
_config_cache = {"mtime": 0, "data": {}}
_config_reload_interval = 60


def now_hkt():
    """Current time in Hong Kong timezone."""
    return datetime.datetime.now(HKT)


def config():
    """Load config.json with caching and hot-reload support."""
    global _config_cache
    config_path = os.path.join(CFG_DIR, "config.json")

    try:
        mtime = os.stat(config_path).st_mtime
    except OSError:
        # Config doesn't exist, return defaults
        return _default_config()

    # Reload if modified or cache expired
    if mtime != _config_cache["mtime"] or time.time() - _config_cache.get("loaded_at", 0) > _config_reload_interval:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            _config_cache = {
                "mtime": mtime,
                "data": data,
                "loaded_at": time.time()
            }
        except Exception as e:
            print(f"Failed to load config.json: {e}", flush=True)
            if not _config_cache.get("data"):
                return _default_config()

    return _config_cache["data"]


def _default_config():
    """Default configuration when config.json doesn't exist."""
    return {
        "models": {
            "deepseek-chat": {
                "provider": "deepseek",
                "display_name": "DeepSeek Chat",
                "description": "快速回應，不顯示推理過程",
                "api_url": "https://api.deepseek.com/chat/completions",
                "enabled": True,
                "default": True,
                "params": {"thinking": {"type": "disabled"}},
                "max_tokens": 900,
                "temperature": 0.7,
                "timeout_seconds": 28,
                "student_limits": {
                    "per_lesson_hour": 10,
                    "per_lesson_day": 25,
                    "per_student_day": 60,
                    "max_question_chars": 200
                },
                "teacher_limits": None
            }
        },
        "global_limits": {
            "student_daily_total": 3000,
            "teacher_daily_total": None
        },
        "open_hours": {
            "timezone": "Asia/Hong_Kong",
            "weekday": ["07:00", "21:00"],
            "weekend": ["08:00", "20:00"]
        },
        "ui": {
            "show_model_selector": True,
            "show_usage_indicators": True,
            "student_can_switch": True,
            "teacher_shows_infinity": True
        }
    }


def db():
    """Get database connection with model tracking support."""
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(os.path.join(DATA_DIR, "usage.db"), timeout=10)

    # Create or migrate tables
    con.execute("""CREATE TABLE IF NOT EXISTS usage(
        ts INTEGER,
        day TEXT,
        u TEXT,
        lesson TEXT,
        cls INTEGER DEFAULT 0,
        realm TEXT,
        model TEXT DEFAULT 'deepseek-chat'
    )""")

    # Add model column if missing
    try:
        con.execute("ALTER TABLE usage ADD COLUMN model TEXT DEFAULT 'deepseek-chat'")
    except sqlite3.OperationalError:
        pass  # Column already exists

    con.execute("CREATE INDEX IF NOT EXISTS usage_u ON usage(u, day)")
    con.execute("CREATE INDEX IF NOT EXISTS usage_model ON usage(u, model, day)")
    con.execute("CREATE INDEX IF NOT EXISTS usage_lesson_model ON usage(u, lesson, model, ts)")

    # Chat logs with model tracking
    con.execute("""CREATE TABLE IF NOT EXISTS chats(
        ts INTEGER,
        day TEXT,
        u TEXT,
        level TEXT,
        lesson TEXT,
        question TEXT,
        answer TEXT,
        masked INTEGER,
        model TEXT DEFAULT 'deepseek-chat',
        thinking_shown INTEGER DEFAULT 0,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        reasoning_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0
    )""")

    # Add token columns if missing
    for col in ['thinking_shown', 'input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens']:
        try:
            default = 0
            con.execute(f"ALTER TABLE chats ADD COLUMN {col} INTEGER DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    return con


def get_model_config(model_id: str, role: str = "student") -> Optional[Dict[str, Any]]:
    """Get configuration for a specific model with role-based limits.

    Args:
        model_id: Model identifier (e.g., 'deepseek-chat', 'deepseek-reasoner')
        role: User role ('student' or 'teacher')

    Returns:
        Model configuration dict with:
        - id, display_name, description
        - api_url, params, max_tokens, temperature, timeout
        - limits (null for teachers)
        - supports_thinking

        Returns None if model not found or disabled.
    """
    cfg = config()
    models = cfg.get("models", {})

    if model_id not in models:
        return None

    model = models[model_id]
    if not model.get("enabled", False):
        return None

    # Apply role-based limits
    limits_key = "teacher_limits" if role == "teacher" else "student_limits"
    limits = model.get(limits_key)

    # Check if thinking is supported (not explicitly disabled in params)
    thinking_param = model.get("params", {}).get("thinking")
    supports_thinking = not (isinstance(thinking_param, dict) and thinking_param.get("type") == "disabled")

    return {
        "id": model_id,
        "display_name": model.get("display_name", model_id),
        "description": model.get("description", ""),
        "api_url": model.get("api_url", "https://api.deepseek.com/chat/completions"),
        "params": model.get("params", {}),
        "max_tokens": model.get("max_tokens", 900),
        "temperature": model.get("temperature", 0.7),
        "timeout": model.get("timeout_seconds", 40),
        "limits": limits,  # null for teachers
        "supports_thinking": supports_thinking,
        "cost_per_1k": model.get("cost_per_1k_tokens", 0)
    }


def get_available_models(user: str, lesson: str, role: str = "student") -> List[Dict[str, Any]]:
    """Get list of available models for a user with current usage stats.

    Args:
        user: User ID
        lesson: Lesson slug (e.g., 'L4-01')
        role: User role ('student' or 'teacher')

    Returns:
        List of model dicts with:
        - Model config fields
        - limits with current usage (left/max)
        - enabled/default flags
    """
    cfg = config()
    models = cfg.get("models", {})

    result = []
    for model_id, model_data in models.items():
        if not model_data.get("enabled", False):
            continue

        model = get_model_config(model_id, role)
        if not model:
            continue

        # Get current usage for this model
        if role == "teacher" or model["limits"] is None:
            # Teachers have no limits
            model["limits"] = None
        else:
            usage = _get_current_usage(user, lesson, model_id)
            limits = model["limits"]

            model["limits"] = {
                "per_lesson_hour": {
                    "left": max(0, limits["per_lesson_hour"] - usage["lesson_hour"]),
                    "max": limits["per_lesson_hour"]
                },
                "per_lesson_day": {
                    "left": max(0, limits["per_lesson_day"] - usage["lesson_day"]),
                    "max": limits["per_lesson_day"]
                },
                "per_student_day": {
                    "left": max(0, limits["per_student_day"] - usage["student_day"]),
                    "max": limits["per_student_day"]
                },
                "max_question_chars": limits["max_question_chars"]
            }

        model["default"] = model_data.get("default", False)
        result.append(model)

    # Sort: default first, then by display name
    result.sort(key=lambda m: (not m["default"], m["display_name"]))
    return result


def _get_current_usage(user: str, lesson: str, model_id: str) -> Dict[str, int]:
    """Get current usage counts for limit checking."""
    con = db()
    now_ts = int(time.time())
    today = now_hkt().strftime("%Y-%m-%d")
    hour_ago = now_ts - 3600

    # Per-lesson-hour count
    lesson_hour = con.execute(
        "SELECT COUNT(*) FROM usage WHERE u=? AND lesson=? AND model=? AND ts>?",
        (user, lesson, model_id, hour_ago)
    ).fetchone()[0]

    # Per-lesson-day count
    lesson_day = con.execute(
        "SELECT COUNT(*) FROM usage WHERE u=? AND lesson=? AND model=? AND day=?",
        (user, lesson, model_id, today)
    ).fetchone()[0]

    # Per-student-day count (across all lessons)
    student_day = con.execute(
        "SELECT COUNT(*) FROM usage WHERE u=? AND model=? AND day=?",
        (user, model_id, today)
    ).fetchone()[0]

    con.close()
    return {
        "lesson_hour": lesson_hour,
        "lesson_day": lesson_day,
        "student_day": student_day
    }


def check_model_usage(user: str, lesson: str, model_id: str, role: str = "student",
                      in_class: bool = False) -> Dict[str, Any]:
    """Check if user has usage quota left for this model.

    Args:
        user: User ID
        lesson: Lesson slug
        model_id: Model to check
        role: User role
        in_class: Whether user is currently in class (lifts limits)

    Returns:
        {
            "allowed": bool,
            "reason": str | None,  # Why usage was denied
            "limits_after": {...} | None  # Predicted limits after this request
        }
    """
    model = get_model_config(model_id, role)
    if not model:
        return {"allowed": False, "reason": "模型不可用", "limits_after": None}

    # Teachers and in-class students have no limits
    if role == "teacher" or in_class or model["limits"] is None:
        return {"allowed": True, "reason": None, "limits_after": None}

    usage = _get_current_usage(user, lesson, model_id)
    limits = model["limits"]

    # Check per-lesson-hour limit
    if usage["lesson_hour"] >= limits["per_lesson_hour"]:
        return {
            "allowed": False,
            "reason": f"已達本課每小時上限 ({limits['per_lesson_hour']} 次)",
            "limits_after": None
        }

    # Check per-lesson-day limit
    if usage["lesson_day"] >= limits["per_lesson_day"]:
        return {
            "allowed": False,
            "reason": f"已達本課今日上限 ({limits['per_lesson_day']} 次)",
            "limits_after": None
        }

    # Check per-student-day limit
    if usage["student_day"] >= limits["per_student_day"]:
        return {
            "allowed": False,
            "reason": f"已達今日總上限 ({limits['per_student_day']} 次)",
            "limits_after": None
        }

    # Check global daily limit
    cfg = config()
    global_limit = cfg.get("global_limits", {}).get("student_daily_total")
    if global_limit:
        con = db()
        today = now_hkt().strftime("%Y-%m-%d")
        global_count = con.execute(
            "SELECT COUNT(*) FROM usage WHERE day=? AND realm='student'",
            (today,)
        ).fetchone()[0]
        con.close()

        if global_count >= global_limit:
            return {
                "allowed": False,
                "reason": "AI 學伴今日已達全服務上限，明天再試",
                "limits_after": None
            }

    # Usage allowed, calculate predicted limits after this request
    return {
        "allowed": True,
        "reason": None,
        "limits_after": {
            "per_lesson_hour": {
                "left": limits["per_lesson_hour"] - usage["lesson_hour"] - 1,
                "max": limits["per_lesson_hour"]
            },
            "per_lesson_day": {
                "left": limits["per_lesson_day"] - usage["lesson_day"] - 1,
                "max": limits["per_lesson_day"]
            },
            "per_student_day": {
                "left": limits["per_student_day"] - usage["student_day"] - 1,
                "max": limits["per_student_day"]
            }
        }
    }


def record_model_usage(user: str, lesson: str, model_id: str, role: str = "student",
                       in_class: bool = False, tokens: Optional[Dict[str, int]] = None,
                       question: str = "", answer: str = "", masked: bool = False,
                       thinking_shown: bool = False, level: str = "") -> None:
    """Record usage of a model for analytics and limit tracking.

    Args:
        user: User ID
        lesson: Lesson slug
        model_id: Model used
        role: User role
        in_class: Whether in class session
        tokens: Token usage dict with input/output/reasoning/total
        question: User's question (after masking)
        answer: AI's answer
        masked: Whether PII was masked
        thinking_shown: Whether thinking was included in response
        level: Course level (L1-L4, yai)
    """
    con = db()
    now_ts = int(time.time())
    today = now_hkt().strftime("%Y-%m-%d")

    # Record in usage table
    con.execute(
        """INSERT INTO usage(ts, day, u, lesson, cls, realm, model)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (now_ts, today, user, lesson, 1 if in_class else 0, role, model_id)
    )

    # Record in chats table if conversation details provided
    if question or answer:
        tokens = tokens or {}
        con.execute(
            """INSERT INTO chats(
                ts, day, u, level, lesson, question, answer, masked, model,
                thinking_shown, input_tokens, output_tokens, reasoning_tokens, total_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now_ts, today, user, level, lesson, question[:2000], answer[:5000],
             1 if masked else 0, model_id, 1 if thinking_shown else 0,
             tokens.get("input", 0), tokens.get("output", 0),
             tokens.get("reasoning", 0), tokens.get("total", 0))
        )

    con.commit()
    con.close()


def get_default_model(role: str = "student") -> Optional[str]:
    """Get the default model ID for a role.

    Returns:
        Model ID string or None if no default set
    """
    cfg = config()
    models = cfg.get("models", {})

    for model_id, model_data in models.items():
        if model_data.get("enabled") and model_data.get("default"):
            return model_id

    # Fallback: first enabled model
    for model_id, model_data in models.items():
        if model_data.get("enabled"):
            return model_id

    return None


def validate_model_selection(model_id: str, role: str = "student") -> Tuple[bool, Optional[str]]:
    """Validate that a user-supplied model ID is allowed.

    Args:
        model_id: Model ID from client
        role: User role

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    if not model_id or not isinstance(model_id, str):
        return False, "無效的模型 ID"

    model = get_model_config(model_id, role)
    if not model:
        return False, f"模型 {model_id} 不可用"

    cfg = config()
    if role == "student" and not cfg.get("ui", {}).get("student_can_switch", True):
        default = get_default_model(role)
        if model_id != default:
            return False, "學生模式不允許切換模型"

    return True, None


# CLI test/debug interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python model_config.py list [role]")
        print("  python model_config.py check <user> <lesson> <model> [role]")
        print("  python model_config.py record <user> <lesson> <model> [role]")
        print("  python model_config.py usage <user> <lesson> <model>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        role = sys.argv[2] if len(sys.argv) > 2 else "student"
        models = get_available_models("test_user", "test_lesson", role)
        print(json.dumps(models, indent=2, ensure_ascii=False))

    elif command == "check":
        if len(sys.argv) < 5:
            print("Usage: python model_config.py check <user> <lesson> <model> [role]")
            sys.exit(1)
        user, lesson, model = sys.argv[2:5]
        role = sys.argv[5] if len(sys.argv) > 5 else "student"
        result = check_model_usage(user, lesson, model, role)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif command == "record":
        if len(sys.argv) < 5:
            print("Usage: python model_config.py record <user> <lesson> <model> [role]")
            sys.exit(1)
        user, lesson, model = sys.argv[2:5]
        role = sys.argv[5] if len(sys.argv) > 5 else "student"
        record_model_usage(user, lesson, model, role,
                          question="測試問題", answer="測試答案")
        print(f"Recorded usage for {user} on {lesson} with {model}")

    elif command == "usage":
        if len(sys.argv) < 5:
            print("Usage: python model_config.py usage <user> <lesson> <model>")
            sys.exit(1)
        user, lesson, model = sys.argv[2:5]
        usage = _get_current_usage(user, lesson, model)
        print(json.dumps(usage, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
