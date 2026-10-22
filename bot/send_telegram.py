"""
Slanje poruka u Telegram kanal preko bota.

Token i adresa kanala dolaze iz okruženja (GitHub secreti):
  TELEGRAM_TOKEN    oblika 123456789:AAH...   (od @BotFather)
  TELEGRAM_CHAT_ID  @imekanala ili -100...    (bot mora biti admin kanala)

python -m bot.send_telegram --test   pošalje probnu poruku
"""

import os
import re
import sys

import requests

TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")
CHAT_RE = re.compile(r"^(@[A-Za-z][A-Za-z0-9_]{4,}|-?\d+)$")


def check_config() -> list[str]:
    """Provjeri format secreta bez ispisivanja njihovih vrijednosti."""
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    problems = []
    if not token:
        problems.append("TELEGRAM_TOKEN nije postavljen")
    elif not TOKEN_RE.match(token):
        problems.append("TELEGRAM_TOKEN nema oblik broj:niz (provjeri da nisi zamijenio secrete)")
    if not chat:
        problems.append("TELEGRAM_CHAT_ID nije postavljen")
    elif TOKEN_RE.match(chat):
        problems.append("TELEGRAM_CHAT_ID izgleda kao token, a treba biti @imekanala")
    elif not CHAT_RE.match(chat):
        problems.append("TELEGRAM_CHAT_ID treba biti @imekanala ili -100… broj")
    return problems


def call(method: str, data: dict) -> dict:
    """Pozovi Telegram Bot API metodu nad kanalom i vrati `result`."""
    token = os.environ["TELEGRAM_TOKEN"].strip()
    chat = os.environ["TELEGRAM_CHAT_ID"].strip()
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}",
                      data={"chat_id": chat, **data}, timeout=30)
    body = r.json()
    if not body.get("ok"):
        # Telegram opis greške ne sadrži token, pa ga je sigurno ispisati
        hint = ""
        desc = body.get("description", "")
        if "chat not found" in desc:
            hint = " (kanal ne postoji ili je adresa pogrešna)"
        elif "not enough rights" in desc or "not a member" in desc:
            hint = " (dodaj bota u kanal kao administratora s pravom objavljivanja)"
        elif r.status_code == 401:
            hint = " (token nije ispravan)"
        raise RuntimeError(f"Telegram {method}: {r.status_code} {desc}{hint}")
    return body["result"]


def send(text: str, silent: bool = False) -> int:
    """Pošalji HTML poruku u kanal i vrati njen message_id."""
    result = call("sendMessage", {"text": text, "parse_mode": "HTML",
                                  "disable_web_page_preview": True,
                                  "disable_notification": silent})
    return result["message_id"]


def main() -> int:
    problems = check_config()
    if problems:
        for p in problems:
            print("GREŠKA:", p)
        return 1
    if "--test" in sys.argv:
        send("Probna poruka: bot je povezan. Prave prognoze stižu uskoro.")
        print("Probna poruka poslana.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
