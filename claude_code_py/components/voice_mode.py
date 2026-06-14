"""Voice Mode — Voice input support for the REPL.

Inspired by the official Claude Code voice mode.
This is a stub implementation that can be extended with speech-to-text libraries.
"""

from __future__ import annotations

import sys
import os
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

from claude_code_py.components.dialog import notification_dialog


# ── Color palette ────────────────────────────────────────────────────────────
from claude_code_py.themes import (
    CLAUDE_ORANGE, CLAUDE_LIGHT, CLAUDE_DIM,
    ACCENT_GREEN, ACCENT_YELLOW, ACCENT_RED,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
)

console = Console()


def is_voice_available() -> bool:
    """Check if voice input is available."""
    try:
        import speech_recognition  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe_microphone(timeout: int = 5, phrase_time_limit: int = 10) -> str | None:
    """Record audio from microphone and transcribe it.

    Requires the 'speech_recognition' package:
        pip install SpeechRecognition

    Args:
        timeout: Max seconds to wait for speech to start.
        phrase_time_limit: Max seconds for a phrase.

    Returns:
        Transcribed text, or None on failure/cancellation.
    """
    try:
        import speech_recognition as sr
    except ImportError:
        notification_dialog(
            "Voice Unavailable",
            "Install SpeechRecognition: pip install SpeechRecognition",
            "warning",
        )
        return None

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            console.print(f"  [{CLAUDE_DIM}]🎤 Listening... (timeout: {timeout}s)[/]", end="\r")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                console.print(f"  [{ACCENT_YELLOW}]⚠ No speech detected.[/]")
                return None
    except OSError as e:
        notification_dialog("Microphone Error", f"Could not access microphone: {e}", "error")
        return None
    except Exception as e:
        notification_dialog("Voice Error", str(e), "error")
        return None

    console.print(f"  [{CLAUDE_DIM}]🎤 Transcribing...[/]", end="\r")

    try:
        # Try Google Speech Recognition (free, no API key)
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        console.print(f"  [{ACCENT_YELLOW}]⚠ Could not understand audio.[/]")
        return None
    except sr.RequestError as e:
        # If Google fails, try offline Sphinx
        try:
            text = recognizer.recognize_sphinx(audio)
            return text
        except Exception:
            notification_dialog("Voice Error", f"Could not reach speech recognition service: {e}", "warning")
            return None
