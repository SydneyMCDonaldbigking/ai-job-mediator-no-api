from __future__ import annotations

import marshal
import sys
from pathlib import Path
from typing import Any

from chainlit.chat_settings import ChatSettings
from chainlit.input_widget import Slider, Switch, TextInput


FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

_PYC_PATH = FRONTEND_DIR / "__pycache__" / "app.cpython-312.pyc"
if not _PYC_PATH.exists():
    raise RuntimeError(f"Missing bootstrap bytecode: {_PYC_PATH}")

with _PYC_PATH.open("rb") as _pyc_file:
    _pyc_file.read(16)
    _bootstrap_code = marshal.load(_pyc_file)

exec(_bootstrap_code, globals())


SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE = "scheduled_scan_settings_form_active"


def normalize_scheduled_scan_settings_input(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(settings.get("scheduled_scan_enabled")),
        "run_time_local": parse_scheduled_scan_field_input(
            "run_time_local",
            str(settings.get("scheduled_scan_run_time_local", "")),
        ),
        "timezone": str(settings.get("scheduled_scan_timezone", "")).strip(),
        "high_score_threshold": parse_scheduled_scan_field_input(
            "high_score_threshold",
            str(settings.get("scheduled_scan_high_score_threshold", "")),
        ),
        "seek_enabled": bool(settings.get("scheduled_scan_seek_enabled")),
        "doda_enabled": bool(settings.get("scheduled_scan_doda_enabled")),
        "boss_enabled": bool(settings.get("scheduled_scan_boss_enabled")),
        "feishu_enabled": bool(settings.get("scheduled_scan_feishu_enabled")),
        "feishu_webhook_url": parse_scheduled_scan_field_input(
            "feishu_webhook_url",
            str(settings.get("scheduled_scan_feishu_webhook_url", "")),
        ),
    }


def build_scheduled_scan_chat_settings(
    config: ScheduledScanConfig,
    assets: MultilingualResumeAssets,
) -> ChatSettings:
    return ChatSettings(
        inputs=[
            Switch(
                id="scheduled_scan_enabled",
                label="开启自动扫描",
                initial=config.enabled,
                tooltip="控制每天自动扫描的总开关",
            ),
            TextInput(
                id="scheduled_scan_run_time_local",
                label="执行时间",
                initial=config.run_time_local,
                placeholder="21:30",
                tooltip="使用 HH:MM 格式，例如 21:30",
            ),
            TextInput(
                id="scheduled_scan_timezone",
                label="时区",
                initial=config.timezone,
                placeholder="Australia/Sydney",
                tooltip="使用 IANA 时区名称",
            ),
            Slider(
                id="scheduled_scan_high_score_threshold",
                label="高分阈值",
                initial=config.high_score_threshold,
                min=0,
                max=1,
                step=0.05,
                tooltip="只有达到这个分数的岗位才会进入高分未投递列表",
            ),
            Switch(
                id="scheduled_scan_seek_enabled",
                label="启用 SEEK",
                initial=config.seek_enabled,
                disabled=not bool(assets.resume_en_id),
                tooltip="需要先上传英文简历",
            ),
            Switch(
                id="scheduled_scan_doda_enabled",
                label="启用 doda",
                initial=config.doda_enabled,
                disabled=not bool(assets.resume_ja_id),
                tooltip="需要先上传日文简历",
            ),
            Switch(
                id="scheduled_scan_boss_enabled",
                label="启用 BOSS直聘",
                initial=config.boss_enabled,
                disabled=not bool(assets.resume_zh_id),
                tooltip="需要先上传中文简历",
            ),
            Switch(
                id="scheduled_scan_feishu_enabled",
                label="启用飞书通知",
                initial=config.feishu_enabled,
                tooltip="发现高分未投递岗位后通过飞书 webhook 推送",
            ),
            TextInput(
                id="scheduled_scan_feishu_webhook_url",
                label="飞书 Webhook",
                initial=config.feishu_webhook_url or "",
                placeholder="https://open.feishu.cn/...",
                tooltip="留空或填 none 会清空 webhook",
            ),
        ]
    )


async def handle_view_scheduled_scan_settings() -> None:
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    result = await backend.get_scheduled_scan_settings()
    content = (
        f"{format_scheduled_scan_settings(result)}\n\n"
        "```yaml\n"
        f"{render_scheduled_scan_config(result.config)}\n"
        "```"
    )
    await cl.Message(
        content=content,
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(result.config)
        + build_discovered_job_actions(result.high_score_unapplied_jobs),
    ).send()


async def handle_start_scheduled_scan_update() -> None:
    result = await backend.get_scheduled_scan_settings()
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, True)
    await cl.Message(
        content=(
            "自动扫描设置已经打开成可视化表单了，你可以直接改开关、时间、阈值和飞书 Webhook，改动会自动保存。\n\n"
            "如果你还是想整段粘贴配置，也可以继续发 YAML/JSON 给我。\n\n"
            "当前配置：\n"
            "```yaml\n"
            f"{render_scheduled_scan_config(result.config)}\n"
            "```"
        ),
        actions=build_tool_actions() + build_scheduled_scan_form_actions(result.config),
    ).send()
    await build_scheduled_scan_chat_settings(result.config, result.assets).send()


async def handle_scheduled_scan_update_submission(user_text: str) -> None:
    edit_field = cl.user_session.get(SESSION_SCHEDULED_SCAN_EDIT_FIELD)
    if edit_field:
        current = await backend.get_scheduled_scan_settings()
        updated_payload = current.config.model_dump(exclude_none=True)
        updated_payload[edit_field] = parse_scheduled_scan_field_input(edit_field, user_text)
        validated = ScheduledScanConfig.model_validate(updated_payload)
    else:
        payload = parse_scheduled_scan_config_input(user_text)
        validated = ScheduledScanConfig.model_validate(payload)
    saved = await backend.update_scheduled_scan_settings(
        validated.model_dump(exclude_none=True)
    )
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    await cl.Message(
        content=(
            f"{format_scheduled_scan_settings(saved)}\n\n"
            "```yaml\n"
            f"{render_scheduled_scan_config(saved.config)}\n"
            "```"
        ),
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(saved.config)
        + build_discovered_job_actions(saved.high_score_unapplied_jobs),
    ).send()


async def handle_toggle_scheduled_scan_field(field: str, value: Any) -> None:
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    current = await backend.get_scheduled_scan_settings()
    payload = current.config.model_dump(exclude_none=True)
    payload[field] = value
    saved = await backend.update_scheduled_scan_settings(payload)
    await cl.Message(
        content=f"已更新 `{field}`。",
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(saved.config)
        + build_discovered_job_actions(saved.high_score_unapplied_jobs),
    ).send()
    await handle_view_scheduled_scan_settings()


async def handle_prompt_scheduled_scan_field(field: str) -> None:
    cl.user_session.set(SESSION_PENDING_ACTION, PENDING_UPDATE_SCHEDULED_SCAN)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, field)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    prompts = {
        "run_time_local": "回复新的每日执行时间，例如 `21:30`。",
        "high_score_threshold": "回复新的高分阈值，例如 `0.85`。",
        "feishu_webhook_url": "回复新的飞书 Webhook 地址；如果要清空就回复 `none`。",
    }
    await cl.Message(
        content=prompts.get(field, "请回复新的字段值。"),
        actions=build_tool_actions(),
    ).send()


async def handle_scheduled_scan_settings_form_update(settings: dict[str, Any]) -> None:
    current = await backend.get_scheduled_scan_settings()
    updated_payload = current.config.model_dump(exclude_none=True)
    updated_payload.update(normalize_scheduled_scan_settings_input(settings))
    validated = ScheduledScanConfig.model_validate(updated_payload)
    saved = await backend.update_scheduled_scan_settings(
        validated.model_dump(exclude_none=True)
    )
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, True)
    await cl.Message(
        content=(
            "自动扫描设置已通过表单保存。\n\n"
            f"{format_scheduled_scan_settings(saved)}\n\n"
            "```yaml\n"
            f"{render_scheduled_scan_config(saved.config)}\n"
            "```"
        ),
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(saved.config)
        + build_discovered_job_actions(saved.high_score_unapplied_jobs),
    ).send()
    await build_scheduled_scan_chat_settings(saved.config, saved.assets).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, Any]) -> None:
    if not cl.user_session.get(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE):
        return
    await handle_scheduled_scan_settings_form_update(settings)
