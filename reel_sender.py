"""
reel_sender.py - दिवसभरात ठराविक वेळांना रोमँटिक/फनी रील्स पाठवतो.

- रील्सच्या लिंक्स reels.txt मध्ये ठेव (एका ओळीत एक लिंक).
- insta_bot.py यातलं maybe_send(...) प्रत्येक poll ला बोलावतो.
"""
import os
import json
import random
import time
from datetime import datetime, timedelta, timezone

from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, PleaseWaitFewMinutes, RateLimitError,
)

FATAL = (LoginRequired, ChallengeRequired, PleaseWaitFewMinutes, RateLimitError)
IST = timezone(timedelta(hours=5, minutes=30))

REELS_PER_WINDOW = int(os.environ.get("REELS_PER_WINDOW", "3"))
MIN_GAP_MIN = 25   # दोन रील्समध्ये किमान इतकी मिनिटं गॅप
REELS_FILE = os.environ.get(
    "REELS_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reels.txt"))

# दिवसाच्या वेळेच्या खिडक्या (IST तास): प्रत्येकीत REELS_PER_WINDOW रील्स
WINDOWS = [(7, 12), (12, 18), (18, 22)]

CAPTIONS = [
    "haha he bagh vedya",
    "he baghun tuchi athvan aali",
    "bagh na, mast aahe ha",
    "he tula pathvaycha hota re",
    "haha he aapla aahe",
    "aww bagh na he",
]


def _load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(path, state):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _load_reels():
    try:
        with open(REELS_FILE, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    except Exception:
        return []


def _plan_day(now):
    """आजच्या पाठवायच्या वेळा ठरवतो (फक्त अजून न गेलेल्या)."""
    cur = now.hour * 60 + now.minute
    times = []
    for start, end in WINDOWS:
        lo, hi = start * 60, end * 60 - 1
        picked = []
        for _ in range(200):            # गॅप पाळून रँडम वेळा निवड
            if len(picked) >= REELS_PER_WINDOW:
                break
            m = random.randint(lo, hi)
            if all(abs(m - x) >= MIN_GAP_MIN for x in picked):
                picked.append(m)
        times += [m for m in picked if m > cur]
    return sorted(times)


def _pick_reel(state, reels):
    used = set(state.get("used", []))
    fresh = [r for r in reels if r not in used]
    if not fresh:                       # सगळ्या वापरून झाल्या, पुन्हा सुरू
        state["used"] = []
        fresh = list(reels)
    url = random.choice(fresh)
    state.setdefault("used", []).append(url)
    return url


def _send(cl, target_pk, url):
    uid = int(target_pk)
    try:
        media_pk = cl.media_pk_from_url(url)
        cl.direct_media_share(str(media_pk), [uid])
    except FATAL:
        raise
    except Exception:
        cl.direct_send(url, user_ids=[uid])   # share न झालं तर लिंक म्हणून पाठव


def maybe_send(cl, target_pk, data_dir, log):
    reels = _load_reels()
    if not reels:
        return

    path = os.path.join(data_dir, "reel_state.json")
    state = _load_state(path)
    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")

    if state.get("date") != today:
        state["date"] = today
        state["pending"] = _plan_day(now)
        _save_state(path, state)
        if state["pending"]:
            log("[REEL] aaj %d reels pathvaychya, vel (IST): %s" % (
                len(state["pending"]),
                ", ".join("%02d:%02d" % divmod(m, 60) for m in state["pending"])))

    pending = state.get("pending", [])
    cur = now.hour * 60 + now.minute
    if not pending or cur < pending[0]:
        return

    pending.pop(0)                      # आधी काढ, म्हणजे एरर आली तरी लूप होणार नाही
    state["pending"] = pending
    url = _pick_reel(state, reels)
    _save_state(path, state)

    try:
        _send(cl, target_pk, url)
        log("[REEL] sent", url)
        if random.random() < 0.6:
            time.sleep(random.uniform(3, 8))
            cl.direct_send(random.choice(CAPTIONS), user_ids=[int(target_pk)])
    except FATAL:
        raise
    except Exception as e:
        log("[REEL] failed:", str(e)[:150])
