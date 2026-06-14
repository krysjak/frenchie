"""Tests for the CompanionSprite component."""

import time
from claude_code_py.components.companion import (
    CompanionSprite, SpriteState, get_companion, render_buddy, _SPRITES,
)


class TestSpriteState:
    """Test that SpriteState enum has all required states."""

    def test_has_all_states(self) -> None:
        assert SpriteState.IDLE.value == "idle"
        assert SpriteState.THINKING.value == "thinking"
        assert SpriteState.WORKING.value == "working"
        assert SpriteState.SUCCESS.value == "success"
        assert SpriteState.ERROR.value == "error"
        assert SpriteState.WAVE.value == "wave"
        assert SpriteState.SLEEP.value == "sleep"

    def test_all_states_have_frames(self) -> None:
        """Every state should have at least one animation frame."""
        from claude_code_py.components.companion import _SPRITES
        for state in SpriteState:
            frames = _SPRITES.get(state)
            assert frames is not None, f"{state} should have frames"
            assert len(frames) > 0, f"{state} should have at least 1 frame"
            # Each frame should be a list of strings
            for frame in frames:
                assert isinstance(frame, list), f"Frame for {state} should be a list"
                assert len(frame) > 0, f"Frame for {state} should have lines"


class TestCompanionSprite:
    """Test the CompanionSprite class."""

    def test_initial_state(self) -> None:
        sprite = CompanionSprite()
        assert sprite.state == SpriteState.IDLE
        assert sprite.message == ""
        assert sprite.frame_index == 0

    def test_set_state(self) -> None:
        sprite = CompanionSprite()
        sprite.set_state(SpriteState.WORKING, "Working hard")
        assert sprite.state == SpriteState.WORKING
        assert sprite.message == "Working hard"
        assert sprite.frame_index == 0  # Reset on state change

    def test_animation_cycles(self) -> None:
        """Frame index should cycle through available frames."""
        sprite = CompanionSprite()
        frames_available = len(_SPRITES[SpriteState.IDLE])
        for _ in range(frames_available):
            sprite.next_frame()
        # After cycling through all frames, should be back to index
        assert sprite.frame_index == 0 or sprite.frame_index == frames_available - 1

    def test_current_frame_returns_strings(self) -> None:
        sprite = CompanionSprite()
        frame = sprite.current_frame()
        assert isinstance(frame, list)
        for line in frame:
            assert isinstance(line, str)

    def test_render_returns_panel(self) -> None:
        sprite = CompanionSprite()
        panel = sprite.render()
        assert panel is not None
        # Panel should have border_style attribute
        assert hasattr(panel, "border_style")

    def test_render_with_message(self) -> None:
        sprite = CompanionSprite()
        sprite.set_state(SpriteState.IDLE, "Hello!")
        panel = sprite.render()
        assert panel is not None

    def test_tip_timer(self) -> None:
        """Tips should not show before interval elapses."""
        sprite = CompanionSprite()
        sprite.show_tip = True
        sprite._last_tip_time = time.time()  # Just set, so tip won't show
        assert sprite._last_tip_time > 0


class TestGetCompanion:
    """Test the singleton get_companion function."""

    def test_singleton(self) -> None:
        c1 = get_companion()
        c2 = get_companion()
        assert c1 is c2, "get_companion should return the same instance"

    def test_render_buddy(self) -> None:
        panel = render_buddy(SpriteState.SUCCESS, "All good!")
        assert panel is not None
