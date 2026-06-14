"""Tests for the plugin system components."""

import json
import tempfile
from pathlib import Path

from claude_code_py.components.plugin_system import (
    PluginManifest, Plugin, PluginRegistry, get_plugin_registry,
)


class TestPluginManifest:
    """Test PluginManifest dataclass."""

    def test_default_values(self) -> None:
        manifest = PluginManifest(name="my-plugin", version="1.0.0", description="Test")
        assert manifest.name == "my-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.description == "Test"
        assert manifest.author == ""
        assert manifest.entry == "plugin.py"
        assert manifest.tools == []
        assert manifest.commands == []
        assert manifest.requires == []
        assert manifest.config_schema == {}

    def test_from_dict_full(self) -> None:
        data = {
            "name": "test-plugin",
            "version": "2.0.0",
            "description": "A test plugin",
            "author": "Tester",
            "homepage": "https://example.com",
            "entry": "main.py",
            "tools": [{"name": "tool1"}],
            "commands": [{"name": "cmd1"}],
            "requires": ["rich"],
            "config_schema": {"type": "object"},
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "test-plugin"
        assert manifest.version == "2.0.0"
        assert manifest.author == "Tester"
        assert manifest.homepage == "https://example.com"
        assert manifest.entry == "main.py"
        assert len(manifest.tools) == 1
        assert len(manifest.commands) == 1
        assert "rich" in manifest.requires

    def test_from_dict_minimal(self) -> None:
        manifest = PluginManifest.from_dict({})
        assert manifest.name == "unknown"
        assert manifest.version == "0.0.1"


class TestPlugin:
    """Test Plugin dataclass."""

    def test_default_values(self) -> None:
        manifest = PluginManifest(name="p", version="1.0", description="d")
        path = Path("/tmp/test-plugin")
        plugin = Plugin(manifest=manifest, path=path)
        assert plugin.manifest is manifest
        assert plugin.path == path
        assert plugin.enabled is True
        assert plugin.config == {}


class TestPluginRegistry:
    """Test PluginRegistry non-networking methods."""

    def test_initial_state(self) -> None:
        registry = PluginRegistry()
        assert registry.plugins == {}
        assert registry._marketplace_cache is None

    def test_get_plugin_nonexistent(self) -> None:
        registry = PluginRegistry()
        assert registry.get_plugin("nonexistent") is None

    def test_list_plugins_empty(self) -> None:
        registry = PluginRegistry()
        assert registry.list_plugins() == []

    def test_enable_plugin_nonexistent(self) -> None:
        registry = PluginRegistry()
        assert registry.enable_plugin("nonexistent") is False

    def test_disable_plugin_nonexistent(self) -> None:
        registry = PluginRegistry()
        assert registry.disable_plugin("nonexistent") is False

    def test_remove_plugin_nonexistent(self) -> None:
        registry = PluginRegistry()
        assert registry.remove_plugin("nonexistent") is False

    def test_builtin_listings(self) -> None:
        registry = PluginRegistry()
        listings = registry._builtin_listings()
        assert len(listings) >= 1
        names = [l.name for l in listings]
        assert "git-integration" in names
        assert all(l.version for l in listings)

    def test_get_marketplace_listings_fallback(self) -> None:
        """When network is unavailable, should fall back to built-in list."""
        registry = PluginRegistry()
        listings = registry.get_marketplace_listings()
        assert len(listings) >= 1
        assert registry._marketplace_cache is not None

    def test_marketplace_listings_cached(self) -> None:
        registry = PluginRegistry()
        first = registry.get_marketplace_listings()
        # Second call should return cached result (no network)
        second = registry.get_marketplace_listings()
        assert first is second  # Same list object (cached)

    def test_force_refresh_marketplace(self) -> None:
        registry = PluginRegistry()
        registry._marketplace_cache = []
        result = registry.get_marketplace_listings(force_refresh=True)
        assert len(result) >= 1


class TestPluginRegistryWithTempDir:
    """Test PluginRegistry with real (temp) directories."""

    def test_install_from_marketplace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            registry = PluginRegistry()
            manifest = PluginManifest(
                name="test-plugin",
                version="1.0.0",
                description="A test plugin",
                author="Tester",
            )

            result = registry.install_from_marketplace(manifest, home)
            assert result is True

            # Check plugin was registered
            plugin = registry.get_plugin("test-plugin")
            assert plugin is not None
            assert plugin.manifest.name == "test-plugin"
            assert plugin.enabled is True

            # Check files were created
            plugin_dir = home / ".frenchie" / "plugins" / "test-plugin"
            assert plugin_dir.exists()
            assert (plugin_dir / "plugin.json").exists()
            assert (plugin_dir / "plugin.py").exists()

            # Verify manifest content
            manifest_data = json.loads((plugin_dir / "plugin.json").read_text())
            assert manifest_data["name"] == "test-plugin"
            assert manifest_data["version"] == "1.0.0"

    def test_install_then_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            registry = PluginRegistry()
            manifest = PluginManifest(name="removable", version="0.1", description="d")
            registry.install_from_marketplace(manifest, home)

            assert registry.get_plugin("removable") is not None
            removed = registry.remove_plugin("removable")
            assert removed is True
            assert registry.get_plugin("removable") is None

    def test_install_then_enable_disable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            registry = PluginRegistry()
            manifest = PluginManifest(name="toggle", version="0.1", description="d")
            registry.install_from_marketplace(manifest, home)

            assert registry.get_plugin("toggle").enabled is True
            registry.disable_plugin("toggle")
            assert registry.get_plugin("toggle").enabled is False
            registry.enable_plugin("toggle")
            assert registry.get_plugin("toggle").enabled is True


class TestGetPluginRegistry:
    """Test the singleton getter."""

    def test_singleton(self) -> None:
        r1 = get_plugin_registry()
        r2 = get_plugin_registry()
        assert r1 is r2
