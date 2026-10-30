from pathlib import Path
import re

import pytest


SKILL = Path(__file__).parents[2] / "skills" / "hermes-finance" / "SKILL.md"


def test_finance_skill_frontmatter_and_scope():
    text = SKILL.read_text(encoding="utf-8")
    description = re.search(r"^description: (.+)$", text, re.MULTILINE).group(1)
    assert len(description) <= 60
    assert description.endswith(".")
    assert "author: yanwuchen (@yanwuchen), Hermes Agent" in text
    assert "Finance 不创建聊天机器人" in text
    assert "普通聊天保持原 Hermes 路径" in text


@pytest.mark.parametrize("secret", ["密码", "POWER4", "HMAC", "QQ 身份"])
def test_finance_skill_withholds_sensitive_inputs(secret):
    text = SKILL.read_text(encoding="utf-8")
    assert secret in text
    assert "不发送密码、验证码、任务 token、HMAC 或 QQ 身份到模型" in text
