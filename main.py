import io
import os
import base64
import pyperclip
import keyboard
import time
from PIL import ImageGrab
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_URL = os.getenv("API_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("API_KEY", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-vl:2b-instruct")
SHORTCUTS = os.getenv("SHORTCUTS", "ctrl+alt+l").split(",")
CLIENT = OpenAI(base_url=API_URL, api_key=API_KEY)


def sanitize_latex(latex: str) -> str:
    return latex.replace("```latex", "").replace("```", "").replace("$", "").strip()


def convert_screenshot_to_latex():
    start_time = time.perf_counter()

    img = ImageGrab.grabclipboard()
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


def main():
    for shortcut in SHORTCUTS:
        keyboard.add_hotkey(shortcut, convert_screenshot_to_latex)
    keyboard.wait()


if __name__ == "__main__":
    main()
