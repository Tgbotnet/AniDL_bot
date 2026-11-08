#@cantarellabots
import random
from config import RESPONSE_IMAGES

_DEFAULT_IMAGE = "https://ibb.co/ycDYQP5r"


def get_random_image() -> str:
    """Return a random image URL from the configured list."""
    if RESPONSE_IMAGES:
        return random.choice(RESPONSE_IMAGES)
    return _DEFAULT_IMAGE
