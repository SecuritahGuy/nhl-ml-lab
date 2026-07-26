import json
import time
import hashlib
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
CACHE_TTL = 300  # 5 min default


def _key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


async def get(url: str, ttl: int = CACHE_TTL):
    p = _path(_key(url))
    if p.exists():
        age = time.time() - p.stat().st_mtime
        if age < ttl:
            return json.loads(p.read_text())
    return None


async def set(url: str, data):
    p = _path(_key(url))
    p.write_text(json.dumps(data, default=str))
    return data


def clear_all():
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True)