"""Cache the Whisper model so it's loaded once, not per-video."""
from functools import lru_cache


@lru_cache(maxsize=1)
def get_whisper_model():
    import whisper_timestamped as whisper
    return whisper.load_model("base")
