import io
import os
import base64
import pyperclip
import keyboard
from PIL import ImageGrab
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("API_KEY", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-vl:4b")
CLIENT = OpenAI(base_url=API_URL, api_key=API_KEY)


def convert_screenshot_to_latex():
    img = ImageGrab.grabclipboard()

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
                        {
                            "type": "text",
                            "text": "Convert this equation to LaTeX. Output ONLY the raw LaTeX string.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_str}"},
                        },
                    ],
                }
            ],
        )

        latex_result = response.choices[0].message.content.strip()
        latex_result = latex_result.replace("```latex", "").replace("```", "").strip()

        pyperclip.copy(latex_result)
        print(f"LaTeX (also copied to clipboard): {latex_result}")

    except Exception as e:
        print(f"Error: {e}")


keyboard.add_hotkey("ctrl+alt+l", convert_screenshot_to_latex)
keyboard.wait()
