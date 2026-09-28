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

MIN_PER_DAY = int(os.environ.get("REELS_MIN_PER_DAY", "5"))
MAX_PER_DAY = min(int(os.environ.get("REELS_MAX_PER_DAY", "15")), 15)   # कधीच १५ पेक्षा जास्त नाही
MIN_GAP_MIN = 20
DAY_START, DAY_END = 0, 24      # IST: २४ तास, वेळेचं बंधन नाही

# शोधासाठी hashtags: फक्त मराठी आणि हिंदी, प्रकारानुसार (रोमँटिक / इमोशनल / फनी)
TAGS = {
    "romantic": ["marathicouple", "marathilove", "marathiromantic", "hindiromantic",
                 "couplegoals", "lovestatus", "romanticreels", "hindilove"],
    "emotional": ["marathishayari", "hindishayari", "emotionalreels", "marathistatus",
                  "marathiemotional", "hindiemotional", "dilkibaat", "hindistatus"],
    "funny": ["marathicomedy", "marathimemes", "marathireels", "hindicomedy",
              "hindimemes", "hindifunnyreels", "marathifunny", "funnyreelshindi"],
}
TAGS_PER_CATEGORY = int(os.environ.get("REEL_TAGS_PER_CATEGORY", "2"))   # प्रत्येक प्रकारातून रोज किती hashtags
PER_TAG = int(os.environ.get("REEL_PER_TAG", "20"))                       # प्रत्येक hashtag मधून किती रील्स

# भाषा फिल्टर: caption मध्ये देवनागरी (मराठी/हिंदी) किंवा हे शब्द/hashtags हवेतच
LANG_WORDS = ("marathi", "marath", "hindi", "hind", "maharashtra", "pune", "mumbai", "mazha", "majha",
              "tujha", "tula", "mala", "prem", "pyar", "pyaar", "ishq", "dil", "shayari", "yaar", "bhai",
              "mera", "tera", "tu ", "kya", "kahi", "aahe", "ahe")

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


def _lang_ok(m):
    """caption मध्ये देवनागरी किंवा मराठी/हिंदी खुणा असतील तरच घेतो."""
    cap = (getattr(m, "caption_text", "") or "").lower()
    if any("\u0900" <= ch <= "\u097f" for ch in cap):
        return True
    return any(w in cap for w in LANG_WORDS)


def _refresh_pool(cl, state, log):
    """रोमँटिक/इमोशनल/फनी hashtags मधून मराठी-हिंदी रील्स गोळा करतो."""
    used = set(state.get("used", []))
    found = []
    for cat, names in TAGS.items():
        for tag in random.sample(names, min(TAGS_PER_CATEGORY, len(names))):
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
            reels = [str(m.pk) for m in medias
                     if _is_reel(m) and _lang_ok(m) and str(m.pk) not in used]
            log("[REEL] %s #%s -> %d reels" % (cat, tag, len(reels)))
            found += reels
            time.sleep(random.uniform(2, 5))
    random.shuffle(found)
    state["pool"] = list(dict.fromkeys(found))


def _plan_day(now):
    """आज किती रील्स (MIN ते MAX रँडम) आणि कोणत्या वेळी ते ठरवतो (फक्त अजून न गेलेल्या वेळा)."""
    total = random.randint(min(MIN_PER_DAY, MAX_PER_DAY), MAX_PER_DAY)
    cur = now.hour * 60 + now.minute
    lo, hi = max(DAY_START * 60, cur + 1), DAY_END * 60 - 1
    if hi <= lo:
        return []
    # दिवस जितका उरलाय तितक्या प्रमाणात संख्या कमी करतो
    total = max(1, round(total * (hi - lo) / ((DAY_END - DAY_START) * 60)))
    picked = []
    for _ in range(1000):
        if len(picked) >= total:
            break
        m = random.randint(lo, hi)
        if all(abs(m - x) >= MIN_GAP_MIN for x in picked):
            picked.append(m)
    return sorted(picked)


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
            log("[REEL] aaj %d reels pathvaychya (max 15), vel (IST): %s" % (
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
