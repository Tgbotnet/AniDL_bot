#@cantarellabots
from pathlib import Path
import base64
import re

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def is_video_file(filename):
    suffix = Path(filename).suffix.lower()
    return suffix in {'.mp4', '.mkv', '.webm', '.m4v', '.avi', '.mov'}

def encode_data(data: str) -> str:
    """Encode string data to base64."""
    return base64.urlsafe_b64encode(data.encode('utf-8')).decode('utf-8').rstrip('=')

def decode_data(encoded: str) -> str:
    """Decode base64 encoded data."""
    padding = '=' * (4 - len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode('utf-8')).decode('utf-8')
