"""Visual UI components for the Frenchie terminal interface.

Inspired by the React/Ink component system in the official Claude Code,
rewritten for Python/Rich.
"""

from .companion import CompanionSprite, SpriteState, get_companion, render_buddy
from .status_bar import StatusBar, get_status_bar
from .dialog import (
    confirm_dialog,
    permission_dialog,
    input_dialog,
    select_dialog,
    diff_preview_dialog,
    multi_select_dialog,
    notification_dialog,
)
from .progress import ProgressBar, Spinner
from .fuzzy_picker import fuzzy_picker, FuzzyPicker
from .plugin_system import (
    PluginRegistry, Plugin, PluginManifest,
    get_plugin_registry, plugins_list_command, plugins_browse_command,
    plugins_manage_command,
)
from .skills_manager import (
    SkillsManager, Skill,
    skills_list_command, skills_view_command, skills_create_command,
    skills_edit_command, skills_delete_command, skills_export_command,
    skills_import_command,
)
from .sandbox import SandboxManager, get_sandbox_manager, SandboxConfig
from .markdown_renderer import render_markdown, render_code_block, render_diff
from .auto_updater import check_for_updates, check_and_notify, perform_update
from .voice_mode import is_voice_available, transcribe_microphone

__all__ = [
    "CompanionSprite", "SpriteState", "get_companion", "render_buddy",
    "StatusBar", "get_status_bar",
    "confirm_dialog", "permission_dialog", "input_dialog", "select_dialog",
    "diff_preview_dialog", "multi_select_dialog", "notification_dialog",
    "ProgressBar", "Spinner",
    "fuzzy_picker", "FuzzyPicker",
    "PluginRegistry", "Plugin", "PluginManifest",
    "get_plugin_registry", "plugins_list_command", "plugins_browse_command",
    "plugins_manage_command",
    "SkillsManager", "Skill",
    "skills_list_command", "skills_view_command", "skills_create_command",
    "skills_edit_command", "skills_delete_command", "skills_export_command",
    "skills_import_command",
    "SandboxManager", "get_sandbox_manager", "SandboxConfig",
    "render_markdown", "render_code_block", "render_diff",
    "check_for_updates", "check_and_notify", "perform_update",
    "is_voice_available", "transcribe_microphone",
]
