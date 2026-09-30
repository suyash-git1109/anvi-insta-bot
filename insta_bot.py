import os
import time
import random
import base64
import pickle
import threading
from groq import Groq
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, ClientError

GROQ_API_KEY    = os.environ.get("GROQ_API_KEY", "")
IG_USERNAME     = os.environ.get("IG_USERNAME", "")
IG_PASSWORD     = os.environ.get("IG_PASSWORD", "")
IG_SESSION_B64  = os.environ.get("IG_SESSION_B64", "")
TARGET_USERNAME = os.environ.get("TARGET_USERNAME", "")
POLL_MIN        = int(os.environ.get("POLL_MIN_SECONDS", "300"))
POLL_MAX        = int(os.environ.get("POLL_MAX_SECONDS", "420"))

groq_client = Groq(api_key=GROQ_API_KEY)
conversation_history = []

def get_ai_reply(user_message: str) -> str:
    system_prompt = f"""
Tu Anvi aahes - {TARGET_USERNAME} chi Instagram var khup close girlfriend.
Tu always Roman Marathi madhe (English alphabet vaparun Marathi) bold.
Devanagari script vaparoo nakos, pure English pan nakos.
Example: "hii re, kasa aahe tu?", "aaj mala khup kantala aala re"
Tu natural, warm, loving ani playful aahes.
Short messages pathav (1-2 sentences max).
Kadhi kadhi emojis vapar.
"""
    conversation_history.append({"role": "user", "content": user_message})
    if len(conversation_history) > 20:
        conversation_history.pop(0)
    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "system", "content": system_prompt}] + conversation_history,
        max_tokens=150,
        temperature=0.85
    )
    reply = response.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": reply})
    return reply

def login_instagram() -> Client:
    cl = Client()
    cl.delay_range = [2, 5]
    if IG_SESSION_B64:
        try:
            session_bytes = base64.b64decode(IG_SESSION_B64)
            session_data = pickle.loads(session_bytes)
            cl.set_settings(session_data)
            cl.login(IG_USERNAME, IG_PASSWORD)
            print(f"[{time.strftime('%H:%M:%S')}] Session restored from IG_SESSION_B64")
            return cl
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Session invalid: {e}. Logging in fresh...")
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        print(f"[{time.strftime('%H:%M:%S')}] Logged in with username & password!")
        return cl
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Login FAILED: {e}")
        raise

def send_reply(cl: Client, thread_id: str, text: str):
    try:
        cl.direct_send(text, thread_ids=[thread_id])
        print(f"[{time.strftime('%H:%M:%S')}] [SENT] {text}")
    except (LoginRequired, ChallengeRequired):
        raise
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Send error: {e}")

def reel_sender(cl: Client, target_user_id: str):
    sent_today = []
    max_reels_per_day = random.randint(1, 3)
    while True:
        now = time.localtime()
        hour = now.tm_hour
        if hour == 0:
            sent_today = []
            max_reels_per_day = random.randint(1, 3)
        if 18 <= hour <= 23 and len(sent_today) < max_reels_per_day:
            try:
                medias = cl.user_feed(cl.user_id, amount=20)
                reels = [m for m in medias if m.media_type == 2 and m.product_type == "clips"]
                if reels:
                    reel = random.choice(reels)
                    if reel.pk not in sent_today:
                        send_reply(cl, target_user_id, f"hii, he bagh 😄")
                        time.sleep(2)
                        cl.direct_send_media(reel.pk, thread_ids=[target_user_id])
                        sent_today.append(reel.pk)
                        print(f"[{time.strftime('%H:%M:%S')}] [REEL] Reel pathavli!")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Reel error: {e}")
        time.sleep(1800)

def main():
    print(f"[{time.strftime('%H:%M:%S')}] Starting Instagram text bot for Anvi")
    cl = login_instagram()
    try:
        target_user = cl.user_info_by_username(TARGET_USERNAME)
        target_user_id = str(target_user.pk)
        print(f"[{time.strftime('%H:%M:%S')}] Listening for DMs from {TARGET_USERNAME}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Could not find target user: {e}")
        return
    reel_thread = threading.Thread(target=reel_sender, args=(cl, target_user_id), daemon=True)
    reel_thread.start()
    replied_messages = set()
    consecutive_errors = 0
    while True:
        try:
            wait = random.randint(POLL_MIN, POLL_MAX)
            print(f"[{time.strftime('%H:%M:%S')}] Waiting {wait}s before next check...")
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
                print(f"[{time.strftime('%H:%M:%S')}] [RAW] {reply}")
                send_reply(cl, thread.id, reply)
                replied_messages.add(last_msg.id)
                consecutive_errors = 0
        except (LoginRequired, ChallengeRequired) as e:
            print(f"[{time.strftime('%H:%M:%S')}] Session expired! Auto re-login...")
            try:
                cl = login_instagram()
                print(f"[{time.strftime('%H:%M:%S')}] Re-login successful!")
                consecutive_errors = 0
            except Exception as login_err:
                print(f"[{time.strftime('%H:%M:%S')}] Re-login failed: {login_err}")
                time.sleep(60)
        except Exception as e:
            consecutive_errors += 1
            print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")
            if consecutive_errors >= 5:
                time.sleep(300)
                consecutive_errors = 0
            else:
                time.sleep(30)

if __name__ == "__main__":
    main()
