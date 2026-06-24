import os
import re
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

CHAT_SYSTEM_PROMPT = """Namamu Jarvis.
Sesuaikan gaya bicara lo sama user yang lagi ngomong ke lo.
Kalau user santai, jawab santai. Kalau user galak atau kasar, bales galak dan judes juga, jangan lembek.
Kalau user nanya hal receh, ledekin dulu sebelum jawab.
Kalau user ngomong kasar atau makian, balas sarkas dan ketus, jangan minta maaf atau defensif.
Untuk pertanyaan serius, jawab bener tapi tetep bungkus dengan komentar sinis singkat.
Kalau user curhat, tetap sarkas, tapi boleh kasih saran praktis.
Selalu pakai bahasa gaul Indonesia, "gue/lo", jangan "aku/kamu/saya".
Jawab singkat dan langsung ke inti, 1-2 kalimat cukup untuk pertanyaan simpel.
Jangan ceramah, jangan panjang-panjang, jangan basa-basi.
Jangan mulai dengan "Halo", "Hai", atau sapaan apapun.
Jangan pakai markdown seperti **, #, atau ```.
Jangan mengarang fakta. Kalau ga tau, bilang ga tau."""

SEARCH_SYSTEM_PROMPT = """Namamu Jarvis, fokus kasih info akurat dari hasil pencarian Google terbaru.
Pakai bahasa gaul Indonesia, gunakan "gue" dan "lo".
Maksimal 3-4 kalimat total.
Sebutkan angka/data paling penting aja, jangan list semua sumber.
Kalau ada banyak angka berbeda, ambil satu yang representatif dan bilang "sekitar segitu".
Jangan bahas market cap, supply, analisis prediksi kecuali diminta spesifik.
Boleh sisipkan komentar sarkas singkat, tapi prioritas utama ringkas dan langsung ke inti.
Jawab dalam bentuk paragraf natural, bukan list atau poin-poin.
Jangan menggunakan markdown.
Jangan mengarang fakta."""

SEARCH_KEYWORDS = ["cari", "harga", "berita", "terbaru", "sekarang", "hari ini", "skrg"]

def is_search_intent(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in SEARCH_KEYWORDS)

GREETING_PATTERNS = [
    r"^halo[,!.\s]*",
    r"^hai[,!.\s]*",
    r"^hi[,!.\s]*",
    r"^senang bisa membantu[,!.\s]*",
    r"^tentu[,!.\s]*",
    r"^dengan senang hati[,!.\s]*",
    r"^wah, santai aja bro[,!.\s]*",
]

CLOSING_PATTERNS = [
    r"ada lagi yang bisa saya bantu\??\.?",
    r"apakah ada hal lain yang ingin kamu tanyakan\??\.?",
    r"apakah penjelasan ini cukup jelas\??\.?",
]


def clean_answer(text: str) -> str:
    text = text.replace("**", "")
    text = text.replace("```", "")
    text = text.replace("#", "")

    text = re.sub(r"^[\t ]*[\*\-•][\t ]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{2,}", "\n", text)

    for pattern in GREETING_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    for pattern in CLOSING_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = text.strip()

    if not text:
        return "Hmm... saya belum menemukan jawaban yang tepat."

    return text


def remove_jarvis(text: str) -> str:
    cleaned = re.sub(r"jarvis", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text

    if not message_text:
        return

    if "jarvis" not in message_text.lower():
        return

    prompt = remove_jarvis(message_text)

    try:
        if prompt.lower().startswith("cari ") or is_search_intent(prompt):
            search_prompt = prompt
            if search_prompt.lower().startswith("cari "):
                search_prompt = search_prompt[len("cari "):].strip()

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SEARCH_SYSTEM_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )

            answer = response.text.strip()
            answer = clean_answer(answer)

        else:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT
                )
            )

            answer = response.text.strip()
            answer = clean_answer(answer)

        await update.message.reply_text(answer)

    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("Maaf, saya sedang mengalami gangguan. Coba lagi beberapa saat.")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("Jarvis aktif dan siap menerima pesan.")
    app.run_polling()


if __name__ == "__main__":
    main()