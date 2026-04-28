"""配置和基础设施回归测试"""
import pytest
from datetime import date


class TestSettings:
    """配置加载"""

    def test_settings_loads(self):
        from app.config import settings
        assert settings.tidb_host != ""
        assert settings.tidb_port == 4000
        assert settings.llm_provider in ("openai", "anthropic")
        assert settings.llm_model != ""

    def test_bge_model_path_defaults(self):
        from app.config import Settings
        s = Settings()
        assert s.bge_model_path == "data/bge-small-zh-v1.5"


class TestSystemPrompt:
    """动态系统提示词"""

    def test_includes_todays_date(self):
        from app.agent.prompt import get_system_prompt
        today = date.today().isoformat()
        prompt = get_system_prompt()
        assert today in prompt, f"prompt should contain today's date {today}"

    def test_includes_confirmation_rules(self):
        from app.agent.prompt import get_system_prompt
        prompt = get_system_prompt()
        assert "show_confirm_card" in prompt
        assert "save_record" in prompt
        assert "确认" in prompt

    def test_includes_meal_type_rules(self):
        from app.agent.prompt import get_system_prompt
        prompt = get_system_prompt()
        assert "早餐" in prompt
        assert "午餐" in prompt
        assert "晚餐" in prompt


class TestJWT:
    """JWT 令牌"""

    def test_create_and_verify(self):
        from app.middleware import create_token, verify_token
        token = create_token(42)
        uid = verify_token(token)
        assert uid == 42

    def test_invalid_token_raises(self):
        from app.middleware import verify_token
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            verify_token("this.is.not.a.valid.jwt")
        assert exc.value.status_code == 401

    def test_token_for_user_1(self):
        from app.middleware import create_token
        token = create_token(1)
        assert len(token) > 20
        assert token.count(".") == 2
