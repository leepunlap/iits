#!/usr/bin/env python3
"""Tests for model configuration system."""
import unittest
import tempfile
import shutil
import os
import json
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))
import model_config


class TestModelConfig(unittest.TestCase):
    """Test model configuration and usage tracking."""

    def setUp(self):
        """Create temporary directories for test data."""
        self.temp_dir = tempfile.mkdtemp()
        self.cfg_dir = os.path.join(self.temp_dir, "config")
        self.data_dir = os.path.join(self.temp_dir, "data")
        os.makedirs(self.cfg_dir)
        os.makedirs(self.data_dir)

        # Override module paths
        model_config.CFG_DIR = self.cfg_dir
        model_config.DATA_DIR = self.data_dir

        # Reset cache
        model_config._config_cache = {"mtime": 0, "data": {}}

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir)

    def write_config(self, config_dict):
        """Write a config.json for testing."""
        config_path = os.path.join(self.cfg_dir, "config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f)

    def test_default_config_when_missing(self):
        """Default config is returned when config.json doesn't exist."""
        cfg = model_config.config()
        self.assertIn("models", cfg)
        self.assertIn("deepseek-chat", cfg["models"])

    def test_load_custom_config(self):
        """Custom config.json is loaded correctly."""
        custom = {
            "models": {
                "test-model": {
                    "provider": "test",
                    "display_name": "Test Model",
                    "enabled": True
                }
            }
        }
        self.write_config(custom)

        cfg = model_config.config()
        self.assertIn("test-model", cfg["models"])
        self.assertEqual(cfg["models"]["test-model"]["display_name"], "Test Model")

    def test_get_model_config_student(self):
        """get_model_config returns correct limits for students."""
        self.write_config({
            "models": {
                "deepseek-chat": {
                    "provider": "deepseek",
                    "display_name": "DeepSeek Chat",
                    "enabled": True,
                    "params": {"thinking": {"type": "disabled"}},
                    "student_limits": {
                        "per_lesson_hour": 10,
                        "per_lesson_day": 25,
                        "per_student_day": 60,
                        "max_question_chars": 200
                    },
                    "teacher_limits": None
                }
            }
        })

        model = model_config.get_model_config("deepseek-chat", role="student")
        self.assertIsNotNone(model)
        self.assertEqual(model["display_name"], "DeepSeek Chat")
        self.assertIsNotNone(model["limits"])
        self.assertEqual(model["limits"]["per_lesson_hour"], 10)
        self.assertFalse(model["supports_thinking"])

    def test_get_model_config_teacher(self):
        """get_model_config returns null limits for teachers."""
        self.write_config({
            "models": {
                "deepseek-chat": {
                    "provider": "deepseek",
                    "display_name": "DeepSeek Chat",
                    "enabled": True,
                    "student_limits": {
                        "per_lesson_hour": 10,
                        "per_lesson_day": 25,
                        "per_student_day": 60,
                        "max_question_chars": 200
                    },
                    "teacher_limits": None
                }
            }
        })

        model = model_config.get_model_config("deepseek-chat", role="teacher")
        self.assertIsNotNone(model)
        self.assertIsNone(model["limits"])  # Teachers have no limits

    def test_get_model_config_disabled(self):
        """Disabled models return None."""
        self.write_config({
            "models": {
                "disabled-model": {
                    "provider": "test",
                    "enabled": False
                }
            }
        })

        model = model_config.get_model_config("disabled-model", role="student")
        self.assertIsNone(model)

    def test_get_model_config_nonexistent(self):
        """Non-existent models return None."""
        self.write_config({"models": {}})
        model = model_config.get_model_config("nonexistent", role="student")
        self.assertIsNone(model)

    def test_supports_thinking_detection(self):
        """supports_thinking is correctly detected from params."""
        self.write_config({
            "models": {
                "with-thinking": {
                    "provider": "deepseek",
                    "enabled": True,
                    "params": {},
                    "student_limits": {"per_lesson_hour": 5}
                },
                "without-thinking": {
                    "provider": "deepseek",
                    "enabled": True,
                    "params": {"thinking": {"type": "disabled"}},
                    "student_limits": {"per_lesson_hour": 10}
                }
            }
        })

        with_thinking = model_config.get_model_config("with-thinking", role="student")
        self.assertTrue(with_thinking["supports_thinking"])

        without_thinking = model_config.get_model_config("without-thinking", role="student")
        self.assertFalse(without_thinking["supports_thinking"])

    def test_get_available_models_student(self):
        """get_available_models returns enabled models for students."""
        self.write_config({
            "models": {
                "model-a": {
                    "provider": "test",
                    "display_name": "Model A",
                    "enabled": True,
                    "default": True,
                    "student_limits": {
                        "per_lesson_hour": 10,
                        "per_lesson_day": 25,
                        "per_student_day": 60,
                        "max_question_chars": 200
                    }
                },
                "model-b": {
                    "provider": "test",
                    "display_name": "Model B",
                    "enabled": True,
                    "default": False,
                    "student_limits": {
                        "per_lesson_hour": 5,
                        "per_lesson_day": 15,
                        "per_student_day": 30,
                        "max_question_chars": 150
                    }
                },
                "model-disabled": {
                    "provider": "test",
                    "enabled": False
                }
            }
        })

        models = model_config.get_available_models("user1", "lesson1", role="student")
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0]["id"], "model-a")  # Default first
        self.assertTrue(models[0]["default"])
        self.assertEqual(models[1]["id"], "model-b")
        self.assertFalse(models[1]["default"])

    def test_get_available_models_teacher(self):
        """Teachers see null limits for all models."""
        self.write_config({
            "models": {
                "model-a": {
                    "provider": "test",
                    "display_name": "Model A",
                    "enabled": True,
                    "student_limits": {"per_lesson_hour": 10},
                    "teacher_limits": None
                }
            }
        })

        models = model_config.get_available_models("teacher1", "lesson1", role="teacher")
        self.assertEqual(len(models), 1)
        self.assertIsNone(models[0]["limits"])

    def test_check_model_usage_allowed(self):
        """check_model_usage allows usage within limits."""
        self.write_config({
            "models": {
                "test-model": {
                    "provider": "test",
                    "enabled": True,
                    "student_limits": {
                        "per_lesson_hour": 10,
                        "per_lesson_day": 25,
                        "per_student_day": 60,
                        "max_question_chars": 200
                    }
                }
            }
        })

        result = model_config.check_model_usage("user1", "lesson1", "test-model", role="student")
        self.assertTrue(result["allowed"])
        self.assertIsNone(result["reason"])
        self.assertIsNotNone(result["limits_after"])
        self.assertEqual(result["limits_after"]["per_lesson_hour"]["left"], 9)

    def test_check_model_usage_hour_limit(self):
        """check_model_usage denies when hourly limit reached."""
        self.write_config({
            "models": {
                "test-model": {
                    "provider": "test",
                    "enabled": True,
                    "student_limits": {
                        "per_lesson_hour": 2,
                        "per_lesson_day": 25,
                        "per_student_day": 60
                    }
                }
            }
        })

        # Record 2 uses in the past hour
        model_config.record_model_usage("user1", "lesson1", "test-model", role="student")
        model_config.record_model_usage("user1", "lesson1", "test-model", role="student")

        result = model_config.check_model_usage("user1", "lesson1", "test-model", role="student")
        self.assertFalse(result["allowed"])
        self.assertIn("每小時上限", result["reason"])

    def test_check_model_usage_day_limit(self):
        """check_model_usage denies when daily lesson limit reached."""
        self.write_config({
            "models": {
                "test-model": {
                    "provider": "test",
                    "enabled": True,
                    "student_limits": {
                        "per_lesson_hour": 100,
                        "per_lesson_day": 2,
                        "per_student_day": 60
                    }
                }
            }
        })

        # Record 2 uses today
        model_config.record_model_usage("user1", "lesson1", "test-model", role="student")
        model_config.record_model_usage("user1", "lesson1", "test-model", role="student")

        result = model_config.check_model_usage("user1", "lesson1", "test-model", role="student")
        self.assertFalse(result["allowed"])
        self.assertIn("今日上限", result["reason"])

    def test_check_model_usage_teacher_unlimited(self):
        """Teachers have unlimited usage."""
        self.write_config({
            "models": {
                "test-model": {
                    "provider": "test",
                    "enabled": True,
                    "student_limits": {"per_lesson_hour": 1},
                    "teacher_limits": None
                }
            }
        })

        # Record many uses
        for _ in range(100):
            model_config.record_model_usage("teacher1", "lesson1", "test-model", role="teacher")

        result = model_config.check_model_usage("teacher1", "lesson1", "test-model", role="teacher")
        self.assertTrue(result["allowed"])
        self.assertIsNone(result["limits_after"])

    def test_check_model_usage_in_class(self):
        """In-class usage is unlimited."""
        self.write_config({
            "models": {
                "test-model": {
                    "provider": "test",
                    "enabled": True,
                    "student_limits": {"per_lesson_hour": 1}
                }
            }
        })

        # Record one use
        model_config.record_model_usage("user1", "lesson1", "test-model", role="student")

        # Check with in_class=True
        result = model_config.check_model_usage("user1", "lesson1", "test-model",
                                               role="student", in_class=True)
        self.assertTrue(result["allowed"])

    def test_record_model_usage(self):
        """record_model_usage stores data correctly."""
        self.write_config({"models": {"test-model": {"enabled": True}}})

        model_config.record_model_usage(
            user="user1",
            lesson="lesson1",
            model_id="test-model",
            role="student",
            tokens={"input": 100, "output": 50, "reasoning": 200, "total": 350},
            question="測試問題",
            answer="測試答案",
            masked=True,
            thinking_shown=True,
            level="L4"
        )

        # Verify in database
        con = model_config.db()
        usage = con.execute("SELECT * FROM usage WHERE u='user1'").fetchone()
        self.assertIsNotNone(usage)
        self.assertEqual(usage[3], "lesson1")  # lesson column
        self.assertEqual(usage[6], "test-model")  # model column

        chat = con.execute("SELECT * FROM chats WHERE u='user1'").fetchone()
        self.assertIsNotNone(chat)
        self.assertEqual(chat[5], "測試問題")  # question
        self.assertEqual(chat[6], "測試答案")  # answer
        self.assertEqual(chat[8], "test-model")  # model
        self.assertEqual(chat[9], 1)  # thinking_shown
        self.assertEqual(chat[10], 100)  # input_tokens
        self.assertEqual(chat[11], 50)  # output_tokens
        self.assertEqual(chat[12], 200)  # reasoning_tokens
        self.assertEqual(chat[13], 350)  # total_tokens

        con.close()

    def test_get_default_model(self):
        """get_default_model returns the default-marked model."""
        self.write_config({
            "models": {
                "model-a": {
                    "provider": "test",
                    "enabled": True,
                    "default": False
                },
                "model-b": {
                    "provider": "test",
                    "enabled": True,
                    "default": True
                }
            }
        })

        default = model_config.get_default_model()
        self.assertEqual(default, "model-b")

    def test_get_default_model_fallback(self):
        """get_default_model falls back to first enabled if no default."""
        self.write_config({
            "models": {
                "model-a": {
                    "provider": "test",
                    "enabled": True,
                    "default": False
                }
            }
        })

        default = model_config.get_default_model()
        self.assertEqual(default, "model-a")

    def test_validate_model_selection_valid(self):
        """validate_model_selection allows valid models."""
        self.write_config({
            "models": {
                "test-model": {
                    "provider": "test",
                    "enabled": True
                }
            }
        })

        is_valid, error = model_config.validate_model_selection("test-model", role="student")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_model_selection_invalid(self):
        """validate_model_selection rejects invalid models."""
        self.write_config({"models": {}})

        is_valid, error = model_config.validate_model_selection("nonexistent", role="student")
        self.assertFalse(is_valid)
        self.assertIn("不可用", error)

    def test_validate_model_selection_student_cant_switch(self):
        """Students can't switch models if ui.student_can_switch=false."""
        self.write_config({
            "models": {
                "model-a": {
                    "provider": "test",
                    "enabled": True,
                    "default": True
                },
                "model-b": {
                    "provider": "test",
                    "enabled": True,
                    "default": False
                }
            },
            "ui": {
                "student_can_switch": False
            }
        })

        # Default model is allowed
        is_valid, error = model_config.validate_model_selection("model-a", role="student")
        self.assertTrue(is_valid)

        # Non-default model is rejected
        is_valid, error = model_config.validate_model_selection("model-b", role="student")
        self.assertFalse(is_valid)
        self.assertIn("不允許切換", error)

    def test_config_hot_reload(self):
        """Config is reloaded when file changes."""
        self.write_config({
            "models": {
                "model-v1": {"provider": "test", "enabled": True}
            }
        })

        cfg1 = model_config.config()
        self.assertIn("model-v1", cfg1["models"])

        # Wait to ensure mtime changes
        time.sleep(0.1)

        # Update config
        self.write_config({
            "models": {
                "model-v2": {"provider": "test", "enabled": True}
            }
        })

        # Force reload by clearing cache
        model_config._config_cache = {"mtime": 0, "data": {}}

        cfg2 = model_config.config()
        self.assertNotIn("model-v1", cfg2["models"])
        self.assertIn("model-v2", cfg2["models"])


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
