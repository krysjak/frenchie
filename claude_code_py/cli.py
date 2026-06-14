from __future__ import annotations

import os
import sys
import json
from collections.abc import Sequence

import click

from . import __version__
from .commands import command_registry
from .config import RuntimeConfig
from .prompts import load_prompt_bundle
from .logger import get_logger


log = get_logger("cli")


def _apply_early_environment() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    os.environ["COREPACK_ENABLE_AUTO_PIN"] = "0"
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        existing = os.environ.get("NODE_OPTIONS", "")
        max_heap = "--max-old-space-size=8192"
        os.environ["NODE_OPTIONS"] = f"{existing} {max_heap}".strip() if existing else max_heap


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-v", "-V", "--version", prog_name="Frenchie")
@click.option("--dump-system-prompt", is_flag=True, hidden=True)
@click.option("--model", default=None)
@click.option("--safe-mode", is_flag=True, default=False, help="Disable all customizations (FRENCHIE.md, plugins, skills, hooks, MCP)")
@click.option("--effort", type=click.Choice(["low", "medium", "high", "xhigh"]), default=None, help="Set thinking effort level")
@click.pass_context
def app(ctx: click.Context, dump_system_prompt: bool, model: str | None, safe_mode: bool, effort: str | None) -> None:
    _apply_early_environment()
    log.debug("Starting CLI — model=%s, safe_mode=%s, effort=%s", model, safe_mode, effort)
    if safe_mode:
        os.environ["FRENCH_SAFE_MODE"] = "1"
    if effort:
        os.environ["FRENCH_EFFORT"] = effort
    if model:
        # Make a CLI --model override sticky across mid-session config rebuilds.
        os.environ["FRENCH_MODEL"] = model
    config = RuntimeConfig.from_environment(model_override=model)
    ctx.obj = config
    log.info("Config loaded — provider=%s, model=%s, cwd=%s", config.api_provider, config.model, config.cwd)

    if dump_system_prompt:
        bundle = load_prompt_bundle()
        click.echo(bundle.render_system_prompt(model=config.model))
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        command_registry.run_default(config)


@app.command("help")
@click.pass_obj
def help_command(config: RuntimeConfig) -> None:
    command_registry.run("help", config)


@app.command("doctor")
@click.pass_obj
def doctor(config: RuntimeConfig) -> None:
    command_registry.run("doctor", config)


@app.command("status")
@click.pass_obj
def status(config: RuntimeConfig) -> None:
    command_registry.run("status", config)


@app.command("config")
@click.argument("args", nargs=-1)
@click.pass_obj
def config_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("config", config, list(args))


@app.command("settings")
@click.argument("args", nargs=-1)
@click.pass_obj
def settings_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("config", config, list(args))


@app.command("permissions")
@click.argument("args", nargs=-1)
@click.pass_obj
def permissions_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("permissions", config, list(args))


@app.command("allowed-tools")
@click.argument("args", nargs=-1)
@click.pass_obj
def allowed_tools_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("permissions", config, list(args))


@app.command("memory")
@click.argument("args", nargs=-1)
@click.pass_obj
def memory(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("memory", config, list(args))


@app.command("files")
@click.pass_obj
def files(config: RuntimeConfig) -> None:
    command_registry.run("files", config)


@app.command("run")
@click.argument("prompt", nargs=-1)
@click.option("--no-stream", is_flag=True)
@click.pass_obj
def run(config: RuntimeConfig, prompt: Sequence[str], no_stream: bool) -> None:
    command_registry.run("run", config, " ".join(prompt), not no_stream)


@app.command("mcp")
@click.argument("args", nargs=-1)
@click.pass_obj
def mcp(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("mcp", config, list(args))


@app.command("tools")
@click.pass_obj
def tools(config: RuntimeConfig) -> None:
    command_registry.run("tools", config)


@app.command("tool")
@click.argument("name")
@click.argument("payload", required=False)
@click.option("--payload-file", type=click.Path(exists=True, dir_okay=False), default=None)
@click.pass_obj
def tool(config: RuntimeConfig, name: str, payload: str | None, payload_file: str | None) -> None:
    if payload_file:
        with open(payload_file, encoding="utf-8-sig") as handle:
            parsed_payload = json.load(handle)
    else:
        parsed_payload = json.loads(payload or "{}")
    command_registry.run("tool", config, name, parsed_payload)


@app.command("clear")
@click.pass_obj
def clear_command(config: RuntimeConfig) -> None:
    command_registry.run("clear", config)


@app.command("reset", hidden=True)
@click.pass_obj
def reset_command(config: RuntimeConfig) -> None:
    command_registry.run("clear", config)


@app.command("new", hidden=True)
@click.pass_obj
def new_command(config: RuntimeConfig) -> None:
    command_registry.run("clear", config)


@app.command("exit")
@click.pass_obj
def exit_command(config: RuntimeConfig) -> None:
    command_registry.run("exit", config)


@app.command("cost")
@click.pass_obj
def cost_command(config: RuntimeConfig) -> None:
    command_registry.run("cost", config)


@app.command("compact")
@click.pass_obj
def compact_command(config: RuntimeConfig) -> None:
    command_registry.run("compact", config)


@app.command("model")
@click.argument("args", nargs=-1)
@click.pass_obj
def model_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("model", config, list(args))


@app.command("commit")
@click.pass_obj
def commit_command(config: RuntimeConfig) -> None:
    command_registry.run("commit", config)


@app.command("init")
@click.pass_obj
def init_command(config: RuntimeConfig) -> None:
    command_registry.run("init", config)


@app.command("version")
@click.pass_obj
def version_command(config: RuntimeConfig) -> None:
    command_registry.run("version", config)


@app.command("login")
@click.pass_obj
def login_command(config: RuntimeConfig) -> None:
    command_registry.run("login", config)


@app.command("logout")
@click.pass_obj
def logout_command(config: RuntimeConfig) -> None:
    command_registry.run("logout", config)


@app.command("bridge")
@click.argument("args", nargs=-1)
@click.pass_obj
def bridge_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("bridge", config, list(args))


@app.command("remote-control", hidden=True)
@click.argument("args", nargs=-1)
@click.pass_obj
def remote_control_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("bridge", config, list(args))


@app.command("web")
@click.argument("args", nargs=-1)
@click.pass_obj
def web_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("web", config, list(args))


@app.command("desktop", hidden=True)
@click.argument("args", nargs=-1)
@click.pass_obj
def desktop_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("web", config, list(args))


@app.command("cd")
@click.argument("path", required=False)
@click.pass_obj
def cd_command(config: RuntimeConfig, path: str | None) -> None:
    command_registry.run("cd", config, path)


@app.command("usage")
@click.pass_obj
def usage_command(config: RuntimeConfig) -> None:
    command_registry.run("usage", config)


@app.command("diff")
@click.pass_obj
def diff_command(config: RuntimeConfig) -> None:
    command_registry.run("diff", config)


@app.command("code-review")
@click.pass_obj
def code_review_command(config: RuntimeConfig) -> None:
    command_registry.run("code-review", config)


@app.command("resume")
@click.argument("args", nargs=-1)
@click.pass_obj
def resume_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("resume", config, list(args))


@app.command("agents")
@click.argument("args", nargs=-1)
@click.pass_obj
def agents_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("agents", config, list(args))


@app.command("advisor")
@click.argument("args", nargs=-1)
@click.pass_obj
def advisor_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("advisor", config, list(args))


@app.command("effort")
@click.argument("args", nargs=-1)
@click.pass_obj
def effort_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("effort", config, list(args))


@app.command("plugins")
@click.argument("args", nargs=-1)
@click.pass_obj
def plugins_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("plugins", config, list(args))


@app.command("skills")
@click.argument("args", nargs=-1)
@click.pass_obj
def skills_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("skills", config, list(args))


@app.command("sandbox")
@click.argument("args", nargs=-1)
@click.pass_obj
def sandbox_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("sandbox", config, list(args))


@app.command("update")
@click.argument("args", nargs=-1)
@click.pass_obj
def update_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("update", config, list(args))


@app.command("voice")
@click.argument("args", nargs=-1)
@click.pass_obj
def voice_command(config: RuntimeConfig, args: Sequence[str]) -> None:
    command_registry.run("voice", config, list(args))


def main(argv: Sequence[str] | None = None) -> None:
    try:
        app.main(args=list(argv) if argv is not None else sys.argv[1:], prog_name="frenchie")
    except Exception as exc:
        log.exception("Unhandled exception in CLI: %s", exc)
        raise

