
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
        model="llama3-8b-8192",
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
    sent_today = []
    max_reels_per_day = random.randint(5, 20)
    print(f"[{time.strftime('%H:%M:%S')}] [REEL] Aaj {max_reels_per_day} reels pathvnar!")

    while True:
        now = time.localtime()
        hour = now.tm_hour

        # Midnight la reset
        if hour == 0:
            sent_today = []
            max_reels_per_day = random.randint(5, 20)
            print(f"[{time.strftime('%H:%M:%S')}] [REEL] Navin din! Aaj {max_reels_per_day} reels pathvnar!")

        if len(sent_today) < max_reels_per_day:
            try:
                medias = cl.user_feed(cl.user_id, amount=50)
                reels = [m for m in medias if m.media_type == 2 and m.product_type == "clips"]

                if reels:
                    reel = random.choice(reels)
                    if reel.pk not in sent_today:
                        messages = [
                            "haha he bagh 😂😂",
                            "re tu bagh ekda 🥺❤️",
                            "hya sarkha ahe apan 😍",
                            "lol yacha mala hasaycha hota 😂",
                            "ekdum mi sarakha ahe na? 🥹",
                            "aww he bagh re 🫶",
                            "hahaha too much 😂💀",
                            "re mi tujhyasathi pathavli 🥰",
                            "he bagh kiti cute ahe 🥰",
                            "hya sarkha tu aahes exactly 😂❤️",
                            "babu he bagh 😭🔥",
                            "lol me hasate hasate padle 😂",
                        ]
                        msg = random.choice(messages)
                        send_reply(cl, target_user_id, msg)
                        time.sleep(3)
                        cl.direct_send_media(reel.pk, thread_ids=[target_user_id])
                        sent_today.append(reel.pk)
                        print(f"[{time.strftime('%H:%M:%S')}] [REEL] Reel pathavli! ({len(sent_today)}/{max_reels_per_day})")
                        # Natural gap 15 te 45 min
                        gap = random.randint(900, 2700)
                        print(f"[{time.strftime('%H:%M:%S')}] [REEL] Pudchi reel {gap//60} min nantar...")
                        time.sleep(gap)
                    else:
                        time.sleep(300)
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] [REEL] Reels sapadlya nahi, 30 min nantar try...")
                    time.sleep(1800)
            except (LoginRequired, ChallengeRequired):
                print(f"[{time.strftime('%H:%M:%S')}] [REEL] Session expired in reel sender!")
                time.sleep(60)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Reel error: {e}")
                time.sleep(600)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] [REEL] Aaj {max_reels_per_day} reels pathavlya! Kal parat!")
            time.sleep(3600)

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
