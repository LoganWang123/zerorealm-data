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

    assert names.index("Export and validate Public Bundle v1") < names.index(
        "Publish report, images, and Public Bundle to website"
    )
    assert names.index("Generate local publishing images (no Agnes)") < names.index(
        "Publish report, images, and Public Bundle to website"
    )
    assert names.index("Verify production report and images") < names.index(
        "Create or update verified WeChat draft"
    )


def test_workflow_keeps_legacy_mdx_and_bundle_feature_flags():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SYNC_PUBLIC_BUNDLE" in text
    assert "SYNC_LEGACY_DAILY_MDX" in text
    assert "scripts/export_public_bundle.py" in text
    assert "website/data/public-v1" in text
    assert "bundleHash" in text
    assert "WEBSITE_REPO_TOKEN" in text
    assert "secrets.WEBSITE_REPO_TOKEN" in text
    assert "echo $WEBSITE_REPO_TOKEN" not in text
    assert "print(os.environ" not in text
    assert "secrets.AGNES_API_KEY" not in text
    assert "AGNES_API_KEY:" not in text
    assert "python publish.py --channel website" in text
    assert "scripts/check_cross_channel_daily.py" in text
    assert "CROSS_CHANNEL_MISSING" not in text  # code lives in Python module


def test_scheduled_wechat_command_can_only_create_a_draft():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python publish.py --channel wechat" in text
    assert "--publish" not in text
    assert "--notify-followers" not in text
    assert "WECHAT_APPID" in text
    assert "WECHAT_SECRET" in text
