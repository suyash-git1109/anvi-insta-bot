import time
import os
import re
import numpy as np
import soundfile as sf
import torch

# ─── TORCH & TORCHAUDIO COMPATIBILITY FIXES ───────────────
torch.set_num_threads(4)
_orig_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _orig_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

import torchaudio
def _sf_load(filepath, *args, **kwargs):
    data, sr = sf.read(filepath, dtype='float32')
    tensor = torch.from_numpy(data)
    if tensor.ndim == 1:
        tensor = tensor.unsqueeze(0)
    else:
        tensor = tensor.t()
    return tensor, sr
torchaudio.load = _sf_load
# ──────────────────────────────────────────────────────────

from instagrapi import Client
import ollama
from TTS.api import TTS

INSTA_USERNAME   = "stolethemoon_2207"
INSTA_PASSWORD   = "PRIYA@123"
ALLOWED_USERNAME = "suyash_salunke_1109"

VOICE_SAMPLE     = "clean_girl.mp3"
CLEAN_SAMPLE     = "clean_girl_ultra_24k.wav"
SESSION_FILE     = "insta_session.json"

SYSTEM_PROMPT = """You are Anvi, a 21-year-old Maharashtrian college girl chatting on Instagram DM with your boyfriend Suyash.
CRITICAL RULES:
1. Speak ONLY in Roman Marathi (Marathi words typed in English letters).
2. DO NOT SPEAK ENGLISH SENTENCES!
3. Use cute Gen-Z girlfriend slang: "tu", "babu", "re", "jannu". Short 1 sentence only."""

MARATHI_TTS_MAP = {
    "hii babu! kasa ahes re? kiti velane aathvan aali majhi!": "हाय बाबू! कसा आहेस रे? किती वेळाने आठवण आली माझी! मिस यु रे!",
    "bye babu! kaaljee ghe, love you so much re!": "बाय बाबू! काळजी घे, लव्ह यू सो मच रे!",
    "theek ahe re, kaam zalyavar call kar haan!": "ठीक आहे रे, काम झाल्यावर लगेच कॉल कर हान!",
    "ghari basle babu, tuzach vichar kartiye re!": "अरे बाबू, घरी बसलेय, तुझाच विचार करतीये रे... सांग ना काय चाललंय?",
    "ho babu me jevle, tu jevlas ka velevar?": "हो बाबू मी जेवले! तू जेवलास का वेळेवर? काळजी घे!",
    "ghari ahe re babu, tula miss kartiye khup!": "घरी आहे रे बाबू, तुला मिस करतीये खूप! कधी भेटणार आपण?",
    "arre babu, tuzach vichar kartiye me... sang na kay chalay?": "अरे बाबू, तुझाच विचार करतीये मी... सांग ना काय चाललंय?"
}


def prepare_clean_girl_ultra():
    src = VOICE_SAMPLE if os.path.exists(VOICE_SAMPLE) else "voice_sample.wav"
    if os.path.exists(src):
        try:
            data, sr = sf.read(src, dtype='float32')
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            target_sr = 24000
            if sr != target_sr:
                num_samples = int(len(data) * target_sr / sr)
                data = np.interp(
                    np.linspace(0, len(data), num_samples, endpoint=False),
                    np.arange(len(data)),
                    data
                )
                sr = target_sr
            # Auto-trim initial silence
            non_silent = np.where(np.abs(data) > 0.02)[0]
            if len(non_silent) > 0:
                data = data[non_silent[0]:]
            max_samples = int(sr * 12)
            sliced = data[:max_samples] if len(data) > max_samples else data
            max_val = np.max(np.abs(sliced))
            if max_val > 0:
                sliced = sliced / max_val * 0.92
            sf.write(CLEAN_SAMPLE, sliced, sr, subtype='PCM_16')
            print(f"✅ Ultra-Clean Girl Sample Ready: {CLEAN_SAMPLE}")
            return CLEAN_SAMPLE
        except Exception as e:
            print(f"Sample prep error: {e}")
    return src


def convert_to_insta_format(raw_wav, out_wav="final_voice_reply.wav"):
    try:
        data, sr = sf.read(raw_wav, dtype='float32')
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        max_val = np.max(np.abs(data))
        if max_val > 0:
            data = data / max_val * 0.92
        sf.write(out_wav, data, sr, subtype='PCM_16')
        return out_wav
    except Exception as e:
        print(f"Format convert error: {e}")
        return raw_wav


def clean_reply(text):
    text = text.replace('"', '').replace("'", "").strip()
    text = re.sub(r'[\u0900-\u097F]+', '', text).strip()
    lines = text.split("\n")
    cleaned = lines[0].strip()
    words = cleaned.split()
    unique_words = []
    for w in words:
        if not unique_words or w.lower() != unique_words[-1].lower():
            unique_words.append(w)
    return " ".join(unique_words)


def get_ai_reply(history, user_msg):
    msg = user_msg.lower().strip()
    if any(w in msg for w in ["hi", "hii", "heyy", "hello"]):
        return "Hii babu! Kasa ahes re? Kiti velane aathvan aali majhi!"
    if any(w in msg for w in ["bye", "love you", "love u"]):
        return "Bye babu! Kaaljee ghe, love you so much re!"
    if any(w in msg for w in ["busy", "nantar", "later"]):
        return "Theek ahe re, kaam zalyavar call kar haan!"
    if any(w in msg for w in ["kay kartes", "ky kartes", "kay krtes", "kay krt ahes", "ky krt ahes"]):
        return "Ghari basle babu, tuzach vichar kartiye re!"
    if any(w in msg for w in ["jevlas", "jevlis"]):
        return "Ho babu me jevle, tu jevlas ka velevar?"
    if any(w in msg for w in ["kuthe", "kuth ahes"]):
        return "Ghari ahe re babu, tula miss kartiye khup!"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-4:]
    messages.append({"role": "user", "content": user_msg})
    try:
        res = ollama.chat(model='llama3', messages=messages)
        reply = clean_reply(res['message']['content'])
        bad = ["today", "beach", "friends", "planning", "excited"]
        if any(w in reply.lower() for w in bad) or len(reply) < 3:
            return "Arre babu, tuzach vichar kartiye me... sang na kay chalay?"
        return reply
    except:
        return "Haa babu, bol na re... aaiktiye me tula!"


def get_tts_text(roman_text):
    low = roman_text.lower().strip()
    if low in MARATHI_TTS_MAP:
        return MARATHI_TTS_MAP[low]
    return "अरे बाबू, घरीच बसलेय मी... सांग ना तू काय करतोयस?"


def main():
    print("=" * 45)
    print("   ANVI - ULTRA-CLEAN REAL HUMAN GIRL BOT")
    print(f"   Only Replying To: @{ALLOWED_USERNAME}")
    print("=" * 45)

    ref_sample = prepare_clean_girl_ultra()

    print("\n[1/2] XTTS Voice Engine Load Hot Aahe...")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    xtts_model = tts.synthesizer.tts_model
    print("  -> Voice Engine Loaded!")

    print("  -> Extracting Ultra-Clean Human Girl Voice Fingerprint...")
    gpt_cond_latent, speaker_embedding = xtts_model.get_conditioning_latents(
        audio_path=[ref_sample],
        gpt_cond_len=16,          # Maximum Full Vocal Fingerprint!
        max_ref_length=16
    )
    print("  -> ✅ Ultra-Clean Vocal Fingerprint Extracted! 🎤\n")

    print("[2/2] Instagram Login...")
    cl = Client()
    cl.delay_range = [2, 3]

    logged_in = False
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(INSTA_USERNAME, INSTA_PASSWORD)
            logged_in = True
            print("Session login successful!")
        except:
            pass

    if not logged_in:
        cl.login(INSTA_USERNAME, INSTA_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        print("Login Successful!")

    print(f"\n✅ Anvi LIVE as @{INSTA_USERNAME}!")
    print("🎙️ Ultra-Clean Real Human Girl Voice Notes ACTIVE!\n")

    user_histories = {}
    processed_msg_ids = set()

    while True:
        try:
            threads = cl.direct_threads(amount=10)
            for thread in threads:
                if not thread.messages:
                    continue
                last_msg = thread.messages[0]
                if str(last_msg.user_id) == str(cl.user_id):
                    continue
                sender = thread.users[0].username.lower() if thread.users else ""
                if sender != ALLOWED_USERNAME.lower():
                    continue
                if last_msg.id in processed_msg_ids:
                    continue
                user_text = last_msg.text
                if not user_text:
                    continue

                processed_msg_ids.add(last_msg.id)
                print(f"\n📩 Suyash: {user_text}")

                if thread.id not in user_histories:
                    user_histories[thread.id] = []

                reply = get_ai_reply(user_histories[thread.id], user_text)
                print(f"❤️  Anvi Text: {reply}")

                cl.direct_send(reply, thread_ids=[thread.id])
                print("   -> Text sent!")

                tts_script = get_tts_text(reply)
                print(f"🎙️  Girl Voice Script: {tts_script}")

                temp_raw = "raw_voice_reply.wav"
                try:
                    out = xtts_model.inference(
                        text=tts_script,
                        language="hi",
                        gpt_cond_latent=gpt_cond_latent,
                        speaker_embedding=speaker_embedding,
                        speed=0.98,
                        temperature=0.25,         # Ultra-Crisp & Zero-Tremor
                        repetition_penalty=3.5
                    )
                    sf.write(temp_raw, out["wav"], 24000, subtype='PCM_16')
                    final_insta_voice = convert_to_insta_format(temp_raw)
                    cl.direct_send_voice(final_insta_voice, thread_ids=[thread.id])
                    print("   -> 🎙️ ULTRA-CLEAN REAL HUMAN GIRL VOICE SENT!")
                except Exception as e_v:
                    print(f"   [Voice Error]: {e_v}")

                user_histories[thread.id].append({"role": "user", "content": user_text})
                user_histories[thread.id].append({"role": "assistant", "content": reply})

            time.sleep(3)

        except KeyboardInterrupt:
            print("\nBot band kela!"); break
        except Exception as e:
            print(f"[Loop Error] {e}"); time.sleep(5)


if __name__ == "__main__":
    main()