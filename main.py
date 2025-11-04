"""
live_new_pairs_notifier.py
Telegram-Bot + Live Pair Notifier für eine Exchange (z. B. Binance)
Kompatibel mit Python 3.13 und Render Background Worker
"""

import os
import time
import json
import requests
import asyncio
from typing import List, Set
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------- CONFIG ----------------
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "DEIN_TELEGRAM_BOT_TOKEN_HIER"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or "DEINE_CHAT_ID_HIER"
POLL_INTERVAL = 60  # Sekunden
KNOWN_PAIRS_FILE = "known_pairs.json"
EXCHANGE_API_BASE = "https://api.binance.com"  # Beispiel: Binance
# ----------------------------------------

# ---------------- FUNKTIONEN ----------------

def load_known_pairs() -> Set[str]:
    try:
        with open(KNOWN_PAIRS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("pairs", []))
    except FileNotFoundError:
        return set()
    except Exception as e:
        print("Fehler beim Laden der known_pairs:", e)
        return set()


def save_known_pairs(pairs: Set[str]):
    try:
        with open(KNOWN_PAIRS_FILE, "w", encoding="utf-8") as f:
            json.dump({"pairs": sorted(list(pairs))}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Fehler beim Speichern der known_pairs:", e)


def get_all_pairs() -> List[str]:
    """Holt alle aktiven Symbole von Binance."""
    try:
        r = requests.get(EXCHANGE_API_BASE + "/api/v3/exchangeInfo", timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [s.get("symbol") for s in data.get("symbols", []) if s.get("status", "").upper() == "TRADING"]
        return symbols
    except Exception as e:
        print("Fehler beim Abrufen der Paare:", e)
        return []


async def send_telegram_message(app, text: str):
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")
    except Exception as e:
        print("Fehler beim Senden der Telegram-Nachricht:", e)


async def monitor_new_pairs(app):
    """Endlosschleife zum Überwachen neuer Handelspaare."""
    known = load_known_pairs()
    print(f"{len(known)} bekannte Paare geladen.")
    await send_telegram_message(app, f"🤖 Bot gestartet. Überwachung läuft ({len(known)} bekannte Paare).")

    while True:
        try:
            all_pairs = set(get_all_pairs())
            if not all_pairs:
                print("Keine Paare erhalten, warte...")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            new_pairs = all_pairs - known
            if new_pairs:
                now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                for p in sorted(new_pairs):
                    text = f"🆕 Neues Pair entdeckt: <b>{p}</b>\nExchange: Binance\nZeit (UTC): {now}"
                    print("Sende:", text)
                    await send_telegram_message(app, text)
                    await asyncio.sleep(0.5)

                known.update(new_pairs)
                save_known_pairs(known)
                print(f"{len(new_pairs)} neue Paare gespeichert.")
            else:
                print(f"Keine neuen Paare. Gesamt: {len(all_pairs)}")

        except Exception as e:
            print("Fehler in Hauptschleife:", e)

        await asyncio.sleep(POLL_INTERVAL)


# ---------------- TELEGRAM COMMANDS ----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Der Live-Pair-Notifier läuft bereits automatisch im Hintergrund!")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    known = load_known_pairs()
    await update.message.reply_text(f"📊 Bekannte Paare: {len(known)}\nPolling-Intervall: {POLL_INTERVAL}s")


# ---------------- HAUPTLAUF ----------------

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))

    # Starte Monitoring im Hintergrund
    asyncio.create_task(monitor_new_pairs(app))

    print("Bot läuft mit Polling...")
    await app.run_polling()


if __name__ == "__main__":
    # Neue Event Loop für Render / Python 3.13
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
