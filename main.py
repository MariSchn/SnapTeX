import io
import os
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
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-vl:2b-instruct")
SHORTCUTS = [s.strip() for s in os.getenv("SHORTCUTS", "ctrl+alt+l").split(",")]
CLIENT = OpenAI(base_url=API_URL, api_key=API_KEY)
IS_MACOS = platform.system() == "Darwin"


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
    return latex.replace("```latex", "").replace("```", "").replace("$", "").strip()


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
        response = CLIENT.responses.create(
            model=MODEL_NAME,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Convert this equation to LaTeX. Output ONLY the raw LaTeX string.",
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{img_str}",
                        },
                    ],
                }
            ],
        )
    except Exception as e:
        print(f"Error: {e}")

    latex_result = response.output_text.strip()
    latex_result = sanitize_latex(latex_result)
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


def main():
    hotkeys = {to_pynput_hotkey(s): convert_screenshot_to_latex for s in SHORTCUTS}
    print(f"[SnapTeX] Listening for: {', '.join(SHORTCUTS)}")
    with keyboard.GlobalHotKeys(hotkeys) as listener:
        listener.join()


if __name__ == "__main__":
    main()
