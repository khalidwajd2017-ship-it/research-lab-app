import base64
import os

def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        return None

# استكمال بعض الدوال المساعدة الأخرى

