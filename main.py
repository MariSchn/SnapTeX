import io
import os
import re
import base64
import platform
import pyperclip
from pynput import keyboard
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("API_KEY", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "glm-ocr:q8_0")
SHORTCUTS = [s.strip() for s in os.getenv("SHORTCUTS", "ctrl+alt+l").split(",")]
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "256"))
CLIENT = OpenAI(base_url=API_URL, api_key=API_KEY)
IS_MACOS = platform.system() == "Darwin"

PROMPT = "Convert this equation to LaTeX. Output ONLY the raw LaTeX string."

# Page-OCR models transcribe the equation and then keep re-emitting it in
# fenced blocks until they hit the token cap - with glm-ocr that is the
# difference between 0.17s and 1.9s. Harmless for models that stop by
# themselves.
STOP_SEQUENCES = ["\n```", "\n$$"]


def get_clipboard_image():
    if IS_MACOS:
        from AppKit import NSPasteboard, NSPasteboardTypePNG, NSPasteboardTypeTIFF
        from PIL import Image

        pb = NSPasteboard.generalPasteboard()
        data = pb.dataForType_(NSPasteboardTypePNG) or pb.dataForType_(NSPasteboardTypeTIFF)
        if data is None:
            return None
        return Image.open(io.BytesIO(data.bytes().tobytes()))
    else:
        from PIL import ImageGrab

        return ImageGrab.grabclipboard()


def sanitize_latex(latex: str) -> str:
    latex = re.sub(r"```[a-zA-Z]*", "", latex).replace("$", "")
    # Some models put a space before every group: `\mathbf {B}`, `\mu_ {0}`.
    # It compiles, but it is not what you want to paste into a document.
    latex = re.sub(r"(\\[a-zA-Z]+|[_^])\s+\{", r"\1{", latex)
    return latex.strip()


def convert_screenshot_to_latex():
    start_time = time.perf_counter()

    img = get_clipboard_image()
    if img is None:
        print("Detected hotkey! No image in clipboard. Capture something first!")
        return

    buffered = io.BytesIO()
    img.convert("RGB").save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    try:
        response = CLIENT.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_str}"},
                        },
                    ],
                }
            ],
            temperature=0,
            max_tokens=MAX_TOKENS,
            stop=STOP_SEQUENCES,
        )
    except Exception as e:
        print(f"Error: {e}")
        return

    latex_result = sanitize_latex(response.choices[0].message.content or "")
    pyperclip.copy(latex_result)

    end_time = time.perf_counter()
    print(
        f"Converted in {end_time - start_time:.2f} seconds. Result (copied to clipboard): {latex_result}"
    )


def to_pynput_hotkey(shortcut: str) -> str:
    """Convert 'ctrl+alt+l' style to pynput '<ctrl>+<alt>+l' style."""
    aliases = {"option": "alt", "windows": "super"}
    modifiers = {"ctrl", "alt", "shift", "cmd", "super"}
    parts = shortcut.strip().split("+")
    result = []
    for p in parts:
        key = aliases.get(p.lower(), p.lower())
        result.append(f"<{key}>" if key in modifiers else key)
    return "+".join(result)


class GlobalHotKeys(keyboard.GlobalHotKeys):
    """Workaround for pynput 1.8.1 on macOS where the darwin handler passes an
    `injected` argument that GlobalHotKeys._on_press/_on_release don't accept."""

    def _on_press(self, key, injected=False):
        try:
            return super()._on_press(key, injected)
        except TypeError:
            return super()._on_press(key)

    def _on_release(self, key, injected=False):
        try:
            return super()._on_release(key, injected)
        except TypeError:
            return super()._on_release(key)


def main():
    hotkeys = {to_pynput_hotkey(s): convert_screenshot_to_latex for s in SHORTCUTS}
    print(f"[SnapTeX] Listening for: {', '.join(SHORTCUTS)}")
    with GlobalHotKeys(hotkeys) as listener:
        listener.join()


if __name__ == "__main__":
    main()
