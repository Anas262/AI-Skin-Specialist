import base64
import os
import re
import subprocess
import tempfile
from io import BytesIO

from dotenv import load_dotenv
from groq import Groq
from PIL import Image


load_dotenv()


def extract_frame_from_video(video_filepath):
    """Extract a representative single frame from a video file using ffmpeg."""
    temp_img = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    temp_img.close()
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(video_filepath),
            "-ss", "00:00:01",
            "-vframes", "1",
            "-update", "1",
            temp_img.name,
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.exists(temp_img.name) and os.path.getsize(temp_img.name) > 0:
            return temp_img.name
    except Exception:
        pass
    if os.path.exists(temp_img.name):
        try:
            os.remove(temp_img.name)
        except OSError:
            pass
    return None


def encode_image_for_groq(filepath):
    image = Image.open(filepath)
    image.thumbnail((1024, 1024))

    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=75)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def clean_doctor_text(text: str) -> str:
    """Strip markdown formatting and special characters so TTS audio sounds natural."""
    if not text:
        return ""
    # Remove asterisks, hashtags, underscores, backticks
    cleaned = re.sub(r"[\*#_`~]", "", text)
    # Collapse extra whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def brain_of_the_doctor(patient_text, image_filepath=None, video_filepath=None):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("Missing GROQ_API_KEY in .env or environment")

    temp_frame_path = None
    target_image = image_filepath

    # If only video is provided, extract a frame as the visual reference
    if not target_image and video_filepath:
        temp_frame_path = extract_frame_from_video(video_filepath)
        target_image = temp_frame_path

    if not target_image:
        raise ValueError("Visual inspection requires an image or video showing the skin issue.")

    try:
        image_data = encode_image_for_groq(target_image)

        prompt = (
            "You are a confident, natural doctor specializing in skin care. Speak with the reassurance, clarity, and authority of a real doctor. "
            "Limit your entire response to two or three sentences maximum. "
            "Do not use any special characters, symbols, asterisks, bullet points, or markdown formatting in your response because it will be converted directly to spoken audio.\n\n"
            f"Patient description: {patient_text}"
        )

        if video_filepath and not image_filepath:
            prompt += "\nThe visual reference was captured from the patient's uploaded video."
        elif video_filepath and image_filepath:
            prompt += "\nThe patient provided both an image and a video; the image is used as the primary visual reference."

        client = Groq(api_key=groq_api_key)
        response = client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"),
            max_completion_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful skin care medical specialist. Give compassionate, general skin care guidance, not a definitive diagnosis. Never use markdown, bullet points, or emojis.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                            },
                        },
                    ],
                },
            ],
        )

        raw_text = response.choices[0].message.content or ""
        return clean_doctor_text(raw_text)

    finally:
        if temp_frame_path and os.path.exists(temp_frame_path):
            try:
                os.remove(temp_frame_path)
            except OSError:
                pass


# OLD CODE KEPT FOR REFERENCE
# import base64
# import os
# from io import BytesIO
#
# from dotenv import load_dotenv
# from groq import Groq
# from PIL import Image
#
#
# folder = os.path.dirname(__file__)
# env_path = os.path.join(folder, ".env")
# load_dotenv(env_path)
#
# api_key = os.environ.get("GROQ_API_KEY")
# if not api_key:
#     raise ValueError("Missing GROQ_API_KEY in .env or environment")
#
#
# image_path = os.path.join(folder, "sample-image.png")
#
# image = Image.open(image_path)
# image.thumbnail((1024, 1024))
#
# buffer = BytesIO()
# image.convert("RGB").save(buffer, format="JPEG", quality=75)
# image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
#
# client = Groq(api_key=api_key)
#
# response = client.chat.completions.create(
#     model=os.environ.get("GROQ_MODEL", "llama-3.2-11b-vision-preview"),
#     max_completion_tokens=1000,
#     messages=[
#         {
#             "role": "system",
#             "content": "You are a helpful medical assistant. Give general information, not a diagnosis.",
#         },
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "What do you see in this image? Give general skin care advice, not a diagnosis.",
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{image_data}",
#                     },
#                 },
#             ],
#         },
#     ],
# )
#
# print(response.choices[0].message.content)
