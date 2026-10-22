"""
Skala kategorija kvaliteta zraka FHMZ (indeks kvaliteta zraka FBiH).

Izvor: https://www.fhmzbih.gov.ba/latinica/ZRAK/AQI-metodologija.php
Granice su µg/m³, gornja granica uključena. FHMZ ih primjenjuje na SATNE
koncentracije; mi ih primjenjujemo na dnevni prosjek, što je blaže od
satnog indeksa u danima s jakim večernjim vrhom. To piše i u poruci.

Preporuke: https://www.fhmzbih.gov.ba/latinica/ZRAK/AQI-efekti.php
"""

import math

SOURCE = "https://www.fhmzbih.gov.ba/latinica/ZRAK/AQI-metodologija.php"

# (gornja granica, emoji, naziv); FHMZ ne propisuje boje, emoji su naši
SCALE = {
    "pm10": [(15, "🔵", "odličan"), (45, "🟢", "dobar"), (120, "🟡", "umjeren"),
             (195, "🟠", "zagađen"), (270, "🔴", "vrlo zagađen"),
             (math.inf, "🟣", "izuzetno zagađen")],
    "pm2_5": [(5, "🔵", "odličan"), (15, "🟢", "dobar"), (50, "🟡", "umjeren"),
              (90, "🟠", "zagađen"), (140, "🔴", "vrlo zagađen"),
              (math.inf, "🟣", "izuzetno zagađen")],
}

# preporuka FHMZ za osjetljive grupe, po kategoriji
ADVICE_SENSITIVE = {
    "umjeren": "osjetljive grupe neka razmotre manje intenzivnih aktivnosti napolju ako osjete simptome",
    "zagađen": "osjetljive grupe neka smanje fizičke aktivnosti, posebno napolju",
    "vrlo zagađen": "osjetljive grupe neka smanje fizičke aktivnosti napolju; i ostali ako osjete simptome",
    "izuzetno zagađen": "izbjegavajte fizičke aktivnosti napolju",
}


def category(value: float, pollutant: str = "pm10") -> tuple[int, str, str]:
    """(redni broj 1-6, emoji, naziv). Vrijednost se zaokruži na cijeli µg/m³
    jer FHMZ tablica ima cjelobrojne granice (npr. 15 je odličan, 16 dobar)."""
    if value is None or math.isnan(value):
        raise ValueError("nema vrijednosti za kategoriju")
    v = round(value)
    for i, (limit, emoji, name) in enumerate(SCALE[pollutant], start=1):
        if v <= limit:
            return i, emoji, name
    raise AssertionError("nedostižno")
