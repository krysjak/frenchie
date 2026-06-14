"""Tests for the Sandbox system — Docker container isolation."""

from pathlib import Path

from claude_code_py.components.sandbox import (
    SandboxConfig, SandboxResult, SandboxManager, get_sandbox_manager,
    sandbox_run_command, sandbox_check_command,
)


class TestSandboxConfig:
    """Test SandboxConfig dataclass default values."""

    def test_default_values(self) -> None:
        cfg = SandboxConfig()
        assert cfg.image == "python:3.11-slim"
        assert cfg.timeout == 120
        assert cfg.memory_limit == "512m"
        assert cfg.cpu_limit == "1.0"
        assert cfg.network is False
        assert cfg.read_only_root is True
        assert cfg.mount_cwd is True
        assert cfg.env_vars == {}

    def test_custom_config(self) -> None:
        cfg = SandboxConfig(
            image="node:20-slim",
            timeout=60,
            memory_limit="1g",
            cpu_limit="2.0",
            network=True,
            read_only_root=False,
            mount_cwd=False,
            env_vars={"NODE_ENV": "production"},
        )
        assert cfg.image == "node:20-slim"
        assert cfg.timeout == 60
        assert cfg.memory_limit == "1g"
        assert cfg.cpu_limit == "2.0"
        assert cfg.network is True
        assert cfg.read_only_root is False
        assert cfg.mount_cwd is False
        assert cfg.env_vars == {"NODE_ENV": "production"}


class TestSandboxResult:
    """Test SandboxResult dataclass."""

    def test_default_values(self) -> None:
        result = SandboxResult()
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.duration == 0.0
        assert result.error is None
        assert result.container_id is None

    def test_success_result(self) -> None:
        result = SandboxResult(
            stdout="Hello\nWorld\n",
            exit_code=0,
            duration=1.5,
        )
        assert result.stdout == "Hello\nWorld\n"
        assert result.exit_code == 0
        assert result.duration == 1.5

    def test_error_result(self) -> None:
        result = SandboxResult(
            stderr="command not found",
            exit_code=127,
            duration=0.1,
            error="Command failed",
        )
        assert result.stderr == "command not found"
        assert result.exit_code == 127
        assert result.error == "Command failed"


class TestSandboxManager:
    """Test SandboxManager (Docker won't be available in test env)."""

    def test_initial_state(self) -> None:
        manager = SandboxManager()
        assert manager.config is not None
        assert isinstance(manager.config, SandboxConfig)

    def test_is_available_returns_false_in_test(self) -> None:
        """On a typical test runner, Docker is not available."""
        manager = SandboxManager()
        # We can't assume Docker is installed, but the check should work
        assert isinstance(manager.is_available(), bool)

    def test_run_without_docker(self) -> None:
        """When Docker is unavailable, run should return error result."""
        manager = SandboxManager()
        if not manager.is_available():
            result = manager.run("echo hello")
            assert result.error is not None
            assert "Docker" in result.error

    def test_check_environment_without_docker(self) -> None:
        """When Docker is unavailable, check should report issues."""
        manager = SandboxManager()
        checks = manager.check_environment()
        assert len(checks) > 0
        # Should have Docker check with error status
        docker_check = checks[0]
        assert "Docker" in docker_check["check"]

    def test_run_with_timeout_config(self) -> None:
        """Run with custom config should use the passed config."""
        manager = SandboxManager()
        if not manager.is_available():
            cfg = SandboxConfig(timeout=5)
            result = manager.run("sleep 10", config=cfg)
            assert result.error is not None

    def test_custom_cwd_parameter(self) -> None:
        """Run with a cwd should not crash even without Docker."""
        manager = SandboxManager()
        if not manager.is_available():
            result = manager.run("pwd", cwd=Path("/tmp"))
            assert "Docker" in result.error or result.exit_code != 0


class TestGetSandboxManager:
    """Test the singleton getter."""

    def test_singleton(self) -> None:
        m1 = get_sandbox_manager()
        m2 = get_sandbox_manager()
        assert m1 is m2


class TestSandboxHelpers:
    """Test the sandbox helper/command functions."""

    def test_sandbox_run_command_exists(self) -> None:
        assert callable(sandbox_run_command)

    def test_sandbox_check_command_exists(self) -> None:
        assert callable(sandbox_check_command)
