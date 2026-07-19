from pathlib import Path


def test_action_delegates_to_the_host_neutral_gate() -> None:
    text = Path("action/action.yml").read_text()
    assert "fab7 ci-check" in text
    assert "claude" not in text.lower()
