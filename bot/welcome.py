"""
Poruka dobrodošlice u kanalu.

Telegram kanali nemaju automatsku poruku za nove članove, pa dobrodošlica
stoji kao zakačena (pinned) poruka: novi član je vidi na vrhu kanala.
Opis kanala (do 255 znakova) se vidi prije pridruživanja.

python -m bot.welcome           ispiše poruku i opis (ništa ne šalje)
python -m bot.welcome --post    objavi poruku tiho, zakači je i postavi opis
"""

import sys

from bot.send_telegram import call, check_config, send

DASHBOARD = "https://bbasic1.github.io/ZagadjenjeSA/"

WELCOME = f"""👋 <b>Dobro došli u ZagađenkoBot!</b>

Svako veče oko 18:30 stiže prognoza zagađenja zraka u Sarajevu za <b>sutra i prekosutra</b>, po stanicama: Vijećnica, Bjelave, Otoka, Saraj Polje, Ilidža, Vogošća, Hadžići, Ilijaš i Ivan Sedlo.

<b>Kako čitati poruku</b>
🔵 odličan · 🟢 dobar · 🟡 umjeren · 🟠 zagađen · 🔴 vrlo zagađen · 🟣 izuzetno zagađen
Broj je očekivani dnevni prosjek PM10 (µg/m³), a u zagradi raspon u koji očekujemo stvarnu vrijednost. Kategorije prate skalu indeksa kvaliteta zraka FHMZ.

<b>Zašto ovo postoji</b>
Da možete planirati trčanje, šetnju s djecom ili provjetravanje dan unaprijed, a ne tek kad zrak već postane loš.

🧪 <b>Model je eksperimentalan.</b> Uči na prognozama vremena i mjerenjima stanica i ponekad će pogriješiti. Svaku prognozu snimamo prije nego što je mjerenje poznato i javno pratimo tačnost: {DASHBOARD}

<i>Nije zvanični izvor. Zvanična mjerenja uživo: fhmzbih.gov.ba. Podaci: FHMZ, Open-Meteo, CAMS.</i>

Podijelite kanal s nekim kome čist zrak znači! 💚"""

DESCRIPTION = ("Večernja prognoza zagađenja zraka (PM10) u Sarajevu za sutra i "
               "prekosutra, po stanicama. Eksperimentalni model, nije zvanični "
               "izvor. Tačnost javno: " + DASHBOARD)


def main() -> int:
    if "--post" not in sys.argv:
        print(WELCOME)
        print(f"\n--- opis kanala ({len(DESCRIPTION)}/255) ---\n{DESCRIPTION}")
        return 0
    problems = check_config()
    if problems:
        for p in problems:
            print("GREŠKA:", p)
        return 1
    msg_id = send(WELCOME, silent=True)
    print(f"Dobrodošlica poslana (message_id {msg_id}).")
    call("pinChatMessage", {"message_id": msg_id, "disable_notification": True})
    print("Zakačena.")
    try:
        call("setChatDescription", {"description": DESCRIPTION})
        print("Opis kanala postavljen.")
    except RuntimeError as e:
        # isti opis dvaput Telegram vraća kao grešku; to nije problem
        if "not modified" not in str(e):
            raise
        print("Opis kanala je već isti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
