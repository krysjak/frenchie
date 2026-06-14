import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition

kb = KeyBindings()
mode = ["default"]

@Condition
def is_buffer_empty():
    from prompt_toolkit.application import get_app
    app = get_app()
    return not app.current_buffer.text.strip()

@kb.add("tab", filter=is_buffer_empty)
def _toggle(event):
    if mode[0] == "default":
        mode[0] = "plan"
    elif mode[0] == "plan":
        mode[0] = "auto"
    else:
        mode[0] = "default"
    event.app.invalidate()

def get_prompt():
    return HTML(f"<b>mode={mode[0]}</b> > ")

session = PromptSession(key_bindings=kb)

# We just test building/compiling it. Let's make sure it doesn't throw syntax or import errors.
print("Syntax check passed.")
