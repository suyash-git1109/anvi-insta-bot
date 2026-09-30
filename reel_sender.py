import os
import time
import random
import base64
import pickle
import threading
from groq import Groq
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired

GROQ_API_KEY    = os.environ.get("GROQ_API_KEY", "")
IG_USERNAME     = os.environ.get("IG_USERNAME", "")
IG_PASSWORD     = os.environ.get("IG_PASSWORD", "")
IG_SESSION_B64  = os.environ.get("IG_SESSION_B64", "")
TARGET_USERNAME = os.environ.get("TARGET_USERNAME", "")
POLL_MIN        = int(os.environ.get("POLL_MIN_SECONDS", "300"))
POLL_MAX        = int(os.environ.get("POLL_MAX_SECONDS", "420"))

groq_client = Groq(api_key=GROQ_API_KEY)
conversation_history = []

def get_ai_reply(user_message):
    system_prompt = f"""Tu Anvi aahes - {TARGET_USERNAME} chi Instagram var khup close girlfriend.
Tu always Roman Marathi madhe bold. Devanagari nakos, pure English nakos.
Example: "hii re, kasa aahe tu?", "aaj mala khup kantala aala re"
Tu natural, warm, loving ani playful aahes. Short messages (1-2 sentences). Emojis vapar."""
    conversation_history.append({"role": "user", "content": user_message})
    if len(conversation_history) > 20:
        conversation_history.pop(0)
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": system_prompt}] + conversation_history,
        max_tokens=150,
        temperature=0.85
    )
    reply = response.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": reply})
    return reply

def login_instagram():
    cl = Client()
    cl.delay_range = [2, 5]
    if IG_SESSION_B64:
        try:
            session_bytes = base64.b64decode(IG_SESSION_B64)
            session_data = pickle.loads(session_bytes)
            cl.set_settings(session_data)
            cl.login(IG_USERNAME, IG_PASSWORD)
            print(f"[{time.strftime('%H:%M:%S')}] Session restored!")
            return cl
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Session invalid: {e}. Fresh login...")
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        print(f"[{time.strftime('%H:%M:%S')}] Logged in with password!")
        return cl
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Login FAILED: {e}")
        raise

def send_reply(cl, thread_id, text):
    try:
        cl.direct_send(text, thread_ids=[thread_id])
        print(f"[{time.strftime('%H:%M:%S')}] [SENT] {text}")
    except (LoginRequired, ChallengeRequired):
        raise
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Send error: {e}")

def reel_sender(cl, target_user_id):
    MESSAGES = [
        "he bagh na, aapan donghe ase ch aahot 😂❤️",
        "re babu hi reel pahun mala tujhi aathvan aali 🥺",
        "tu ani mi, exactly asech bhandto 😭😂",
        "hya couple sarkhi aapli jodi aahe na? 🥰",
        "he pahilas ka? mi tujhyavar ragavle tar asach hoil 😤😂",
        "aww kiti god aahe he, mala pan asach pahije 🥹❤️",
        "tu mala kadhi asa surprise dilas ka? 😏",
        "ha mulga tujhya sarkha vedha aahe 😂😂",
        "hi mulgi mazya sarkhi nautanki aahe ka? 🙈",
        "he bagh ani mala sang, tu asa karshil ka? 😌",
        "me tula miss kartey, he bagh ani hass 🫶",
        "asach ek date pahije mala tujhyasobat 🥺❤️",
        "tu itka romantic kadhi honar re? 😜",
        "hya reel madhe tuch disla mala 😂😍",
    ]
    HASHTAGS = ["couplegoals", "coupleslove", "cutecouple", "relationshipgoals", "marathicouple"]

    sent_ids = set()
    current_day = time.strftime("%Y-%m-%d")
    sent_today = 0
    daily_limit = random.randint(5, 20)
    print(f"[{time.strftime('%H:%M:%S')}] [REEL] Aaj {daily_limit} reels pathvnar!")

    while True:
        try:
            today = time.strftime("%Y-%m-%d")
            if today != current_day:
                current_day = today
                sent_today = 0
                daily_limit = random.randint(5, 20)
                print(f"[{time.strftime('%H:%M:%S')}] [REEL] Navin din! Aaj {daily_limit} reels pathvnar!")

            if sent_today >= daily_limit:
                print(f"[{time.strftime('%H:%M:%S')}] [REEL] Aaj che {daily_limit} reels zale, kal parat!")
                time.sleep(1800)
                continue

            tag = random.choice(HASHTAGS)
            medias = cl.hashtag_medias_top(tag, amount=30)
            reels = [m for m in medias
                     if m.media_type == 2 and m.product_type == "clips"
                     and str(m.pk) not in sent_ids]

            if not reels:
                print(f"[{time.strftime('%H:%M:%S')}] [REEL] Reels sapadlya nahit, 30 min nantar try...")
                time.sleep(1800)
                continue

            reel = random.choice(reels)
            cl.direct_send(random.choice(MESSAGES), user_ids=[int(target_user_id)])
            time.sleep(3)
            cl.direct_media_share(str(reel.pk), [int(target_user_id)])
            sent_ids.add(str(reel.pk))
            sent_today += 1
            print(f"[{time.strftime('%H:%M:%S')}] [REEL] Pathavli! ({sent_today}/{daily_limit})")

            gap = random.randint(1200, 3000)  # 20 te 50 min
            print(f"[{time.strftime('%H:%M:%S')}] [REEL] Pudchi reel {gap//60} min nantar...")
            time.sleep(gap)

        except (LoginRequired, ChallengeRequired):
            print(f"[{time.strftime('%H:%M:%S')}] [REEL] Session expired in reel sender!")
            time.sleep(300)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [REEL] Error: {e}")
            time.sleep(600)

def main():
    print(f"[{time.strftime('%H:%M:%S')}] Starting Instagram text bot for Anvi")
    cl = login_instagram()

    try:
        target_user = cl.user_info_by_username(TARGET_USERNAME)
        target_user_id = str(target_user.pk)
        print(f"[{time.strftime('%H:%M:%S')}] Listening for DMs from {TARGET_USERNAME}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Target user error: {e}")
        return

    reel_thread = threading.Thread(target=reel_sender, args=(cl, target_user_id), daemon=True)
    reel_thread.start()

    replied_messages = set()
    consecutive_errors = 0

    while True:
        try:
            wait = random.randint(POLL_MIN, POLL_MAX)
            print(f"[{time.strftime('%H:%M:%S')}] Waiting {wait}s...")
            time.sleep(wait)

            threads = cl.direct_threads(amount=10)
            for thread in threads:
                if not thread.messages:
                    continue
                last_msg = thread.messages[0]
                if last_msg.id in replied_messages:
                    continue
                if str(last_msg.user_id) == str(cl.user_id):
                    replied_messages.add(last_msg.id)
                    continue
                thread_user_ids = [str(u.pk) for u in thread.users]
                if target_user_id not in thread_user_ids:
                    continue
                msg_text = ""
                if last_msg.item_type == "text":
                    msg_text = last_msg.text
                elif last_msg.item_type == "reel_share":
                    msg_text = "ek reel pathavli"
                elif last_msg.item_type == "media_share":
                    msg_text = "ek post pathavla"
                else:
                    replied_messages.add(last_msg.id)
                    continue
                print(f"[{time.strftime('%H:%M:%S')}] [MSG] {msg_text}")
                reply = get_ai_reply(msg_text)
                print(f"[{time.strftime('%H:%M:%S')}] [REPLY] {reply}")
                send_reply(cl, thread.id, reply)
                replied_messages.add(last_msg.id)
                consecutive_errors = 0

        except (LoginRequired, ChallengeRequired):
            print(f"[{time.strftime('%H:%M:%S')}] Session expired! Auto re-login...")
            try:
                cl = login_instagram()
                print(f"[{time.strftime('%H:%M:%S')}] Re-login successful!")
                consecutive_errors = 0
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Re-login failed: {e}")
                time.sleep(60)
        except Exception as e:
            consecutive_errors += 1
            print(f"[{time.strftime('%H:%M:%S')}] Error ({consecutive_errors}): {e}")
            if consecutive_errors >= 5:
                time.sleep(300)
                consecutive_errors = 0
            else:
                time.sleep(30)

if __name__ == "__main__":
    main()
