from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/daily-crawl.yaml")


def load_workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_schedule_runs_daily_at_2300_beijing():
    workflow = load_workflow()

    assert workflow[True]["schedule"] == [{"cron": "0 15 * * *"}]


def test_release_generates_media_before_website_and_wechat_draft():
    workflow = load_workflow()
    names = [step.get("name", "") for step in workflow["jobs"]["pipeline"]["steps"]]

    assert names.index("Generate and validate publishing images") < names.index(
        "Publish report and images to website"
    )
    assert names.index("Verify production report and images") < names.index(
        "Create or update verified WeChat draft"
    )


def test_scheduled_wechat_command_can_only_create_a_draft():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python publish.py --channel wechat" in text
    assert "--publish" not in text
    assert "--notify-followers" not in text
    assert "WECHAT_APPID" in text
    assert "WECHAT_SECRET" in text
