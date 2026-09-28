"""
reel_sender.py - रोमँटिक/फनी रील्स आपोआप शोधून दिवसभर ठराविक वेळांना पाठवतो.

- रील्स Instagram च्या hashtags मधून आपोआप निवडतो (लिस्ट द्यायची गरज नाही).
- reels.txt असेल (ऐच्छिक) तर त्यातल्या लिंक्स पण मिक्स होतात.
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
MIN_GAP_MIN = 25
# दिवसाच्या वेळेच्या खिडक्या (IST तास): प्रत्येकीत REELS_PER_WINDOW रील्स
WINDOWS = [(7, 12), (12, 18), (18, 22)]

# शोधासाठी hashtags (Render → Environment मध्ये REEL_HASHTAGS ने बदलता येतात, कॉमाने वेगळे)
DEFAULT_TAGS = ("marathicomedy,marathimemes,marathireels,funnyreels,"
                "couplereels,romanticreels,couplegoals,lovereels")
HASHTAGS = [t.strip().lstrip("#") for t in os.environ.get("REEL_HASHTAGS", DEFAULT_TAGS).split(",") if t.strip()]
TAGS_PER_DAY = int(os.environ.get("REEL_TAGS_PER_DAY", "3"))     # रोज किती hashtags मधून शोधायचं
PER_TAG = int(os.environ.get("REEL_PER_TAG", "15"))              # प्रत्येक hashtag मधून किती रील्स

REELS_FILE = os.environ.get(
    "REELS_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "reels.txt"))

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


def _file_reels():
    try:
        with open(REELS_FILE, "r", encoding="utf-8") as f:
            return [l.strip() for l in f
                    if l.strip() and not l.strip().startswith("#") and "XXXX" not in l and "YYYY" not in l]
    except Exception:
        return []


def _is_reel(m):
    return getattr(m, "media_type", None) == 2 and getattr(m, "product_type", "") == "clips"


def _refresh_pool(cl, state, log):
    """hashtags मधून रील्स गोळा करतो आणि state["pool"] मध्ये ठेवतो."""
    used = set(state.get("used", []))
    found = []
    tags = random.sample(HASHTAGS, min(TAGS_PER_DAY, len(HASHTAGS)))
    for tag in tags:
        medias = []
        for fn in ("hashtag_medias_top", "hashtag_medias_recent"):
            try:
                medias = list(getattr(cl, fn)(tag, amount=PER_TAG))
                if medias:
                    break
            except FATAL:
                raise
            except Exception as e:
                log("[REEL] %s(%s) failed: %s" % (fn, tag, str(e)[:100]))
        reels = [str(m.pk) for m in medias if _is_reel(m) and str(m.pk) not in used]
        log("[REEL] #%s -> %d reels" % (tag, len(reels)))
        found += reels
        time.sleep(random.uniform(2, 5))
    state["pool"] = list(dict.fromkeys(found))    # डुप्लिकेट काढून


def _plan_day(now):
    cur = now.hour * 60 + now.minute
    times = []
    for start, end in WINDOWS:
        lo, hi = start * 60, end * 60 - 1
        picked = []
        for _ in range(200):
            if len(picked) >= REELS_PER_WINDOW:
                break
            m = random.randint(lo, hi)
            if all(abs(m - x) >= MIN_GAP_MIN for x in picked):
                picked.append(m)
        times += [m for m in picked if m > cur]
    return sorted(times)


def _pick(state):
    """pool मधून (किंवा reels.txt मधून) एक रील निवडतो."""
    pool = state.get("pool", [])
    if pool:
        item = pool.pop(random.randrange(len(pool)))
        state["pool"] = pool
        return item
    used = set(state.get("used", []))
    fresh = [u for u in _file_reels() if u not in used]
    if not fresh:
        fresh = _file_reels()
    return random.choice(fresh) if fresh else None


def _send(cl, target_pk, item):
    uid = int(target_pk)
    if str(item).isdigit():                       # media pk
        cl.direct_media_share(str(item), [uid])
        return
    try:                                          # reels.txt मधली लिंक
        cl.direct_media_share(str(cl.media_pk_from_url(item)), [uid])
    except FATAL:
        raise
    except Exception:
        cl.direct_send(item, user_ids=[uid])


def maybe_send(cl, target_pk, data_dir, log):
    path = os.path.join(data_dir, "reel_state.json")
    state = _load_state(path)
    now = datetime.now(IST)
    today = now.strftime("%Y-%m-%d")

    if state.get("date") != today:
        state["date"] = today
        state["pending"] = _plan_day(now)
        state["pool_tried"] = ""
        _save_state(path, state)
        if state["pending"]:
            log("[REEL] aaj %d reels pathvaychya, vel (IST): %s" % (
                len(state["pending"]),
                ", ".join("%02d:%02d" % divmod(m, 60) for m in state["pending"])))

    pending = state.get("pending", [])
    cur = now.hour * 60 + now.minute
    if not pending or cur < pending[0]:
        return

    # पाठवायची वेळ झाली. pool रिकामा असेल तर आजसाठी एकदा शोध
    if not state.get("pool") and state.get("pool_tried") != today:
        state["pool_tried"] = today
        try:
            _refresh_pool(cl, state, log)
        except FATAL:
            _save_state(path, state)
            raise
        _save_state(path, state)

    pending.pop(0)                    # आधी काढ, म्हणजे एरर आली तरी लूप होणार नाही
    state["pending"] = pending
    item = _pick(state)
    if not item:
        log("[REEL] pathvayla reel milali nahi")
        _save_state(path, state)
        return
    state["used"] = (state.get("used", []) + [str(item)])[-300:]
    _save_state(path, state)

    try:
        _send(cl, target_pk, item)
        log("[REEL] sent", item)
        if random.random() < 0.6:
            time.sleep(random.uniform(3, 8))
            cl.direct_send(random.choice(CAPTIONS), user_ids=[int(target_pk)])
    except FATAL:
        raise
    except Exception as e:
        log("[REEL] failed:", str(e)[:150])
