# CLAUDE.md

Prognoza zagađenja zraka u Sarajevu 24 i 48 h unaprijed, po stanici. Telegram bot svako veče šalje prognozu, a javni dashboard prati tačnost uživo. Cilj je pobijediti perzistenciju ("sutra kao danas") i imati jak CV projekat sa stvarnom evaluacijom.

Komuniciraj na bosanskom. Kod piši u Pythonu, a odluke objasni kratko.

## Najvažnije pravilo: bez curenja podataka

- Varijable koje gledaju unaprijed (padavine, vjetar, temperatura, inverzija za t+h) smiju doći **samo iz snimljene prognoze**, nikad iz mjerenja ili reanalize za taj period.
- Za trening koristi prognozu koja je bila dostupna u trenutku izdavanja (`issued_utc` ≤ trenutak prognoze). Ako se trenira na reanalizi (ERA5), u evaluaciji obavezno napiši da je rezultat optimističan.
- Validacija je isključivo klizeća po vremenu (trening uvijek prije testa). Nikad nasumična podjela. Zadnja zima ostaje netaknuta kao završni test.
- Lag varijable mjerenja smiju koristiti samo vrijednosti do trenutka prognoze.

Ako primijetiš kod koji krši ovo, zaustavi se i reci to prije nego nastaviš.

## Model i evaluacija

- **Model:** LightGBM, kvantilna regresija (0.1, 0.5, 0.9), poseban model za horizont 24 h i 48 h (direktna prognoza). Target je dnevni prosjek po stanici, na log skali.
- **Target još nije odlučen:** PM10 (mjere ga sve stanice) ili PM2.5 (samo Bjelave, Otoka, Ilidža, Vogošća, Hadžići). Ne pretpostavljaj, pitaj.
- **Hladan start:** pretreniranje na CAMS arhivi (Open-Meteo Air Quality), pa kalibracija na FHMZ stanicama (model output statistics).
- **Ključne varijable:** perzistencija (lagovi 1 do 72 h), inverzija (T 850 hPa minus T 2 m), vjetar, padavine, visina graničnog sloja, stepen grijanja (ispod 15 °C), sezonalnost, identifikator stanice.
- **Baselineovi koje treba pobijediti:** perzistencija (glavni), klimatologija, sirovi CAMS.
- **Metrike:** MAE (µg/m³), skill score prema perzistenciji, MAE posebno na danima promjene, tačnost kategorije, pokrivenost intervala 0.1 do 0.9 (cilj 80 %).
- **Fallback:** ako model ili podaci zakažu, šalje se perzistencija.
- Kategorije u poruci bota prate zvaničnu skalu (Zavod za javno zdravstvo KS / FHMZ), uz ogradu da bot nije zvaničan izvor.

## Struktura repoa

| Putanja | Šta je |
| --- | --- |
| `collect.py` | Prikupljanje: FHMZ mjerenja + Open-Meteo prognoze (meteo i CAMS PM) za sve stanice |
| `data/fhmz/YYYY-MM.csv` | Satna mjerenja, long format: `station,pollutant,time_utc,value,fetched_at`, bez duplikata |
| `data/forecast/YYYY-MM-DD_00\|12.csv` | Snimci prognoze dvaput dnevno: `issued_utc,station,valid_utc,` meteo varijable, `cams_pm10,cams_pm2_5` |
| `.github/workflows/collect.yml` | GitHub Actions svaka 3 h (minuta 17, UTC), commituje `data/` kao `air-bot` |
| `requirements.txt` | Zavisnosti (Python 3.15 u CI-ju) |
| `.claude/skills/`, `.claude/agents/` | Skillovi (scikit-learn, statsmodels, matplotlib, seaborn, EDA, testiranje) i agenti (`data-scientist`, `data-analyst`, `python-reviewer`, `silent-failure-hunter`) |

Pokretanje lokalno: `pip install -r requirements.txt && python collect.py`.

## Činjenice o podacima

- Sva vremena u fajlovima su **UTC**. FHMZ prikazuje lokalno vrijeme (Europe/Sarajevo), `collect.py` ga pretvara.
- `collect.py` čita stranice pojedinih stanica (`amsXxx.php`), koje daju zadnjih ~7 dana, pa se propušten run sam popuni. Glavna AQI stranica se **ne koristi** jer gubi prazne ćelije.
- Stanice: vijecnica, bjelave, otoka, saraj_polje, ilidza, vogosca, hadzici, ilijas, ivan_sedlo. Ivan Sedlo je planinska stanica iznad kotline, kandidat za mjerenu inverziju (poređenje s Otokom).
- FHMZ podaci imaju rupe (npr. Otoka bez 18. i 19.10.2026). Nedostajuće vrijednosti rješavaj eksplicitno, nikad tiho.
- `issued_utc` u prognozama je vrijeme preuzimanja, ne vrijeme inicijalizacije modela. Snimak počinje od 00 UTC tekućeg dana, pa sati prije `issued_utc` nisu prava prognoza.
- Ne arhiviraj WAQI/aqicn podatke (licenca zabranjuje). Open-Meteo je CC BY 4.0, uz atribuciju.

## Rad na kodu

- Ne mijenjaj format postojećih CSV fajlova bez dogovora; arhiva se ne može ponovo prikupiti.
- Greške ne gutaj tiho: jedna stanica smije pasti bez rušenja ostalih, ali neuspjeh mora biti vidljiv (log i izlazni kod 1).
- Za scraper dodaj testove koji provjeravaju format stranice, jer FHMZ može promijeniti HTML.

## Faze

1. Validacija potražnje (landing stranica, 50 prijava)
2. **Prikupljanje — u toku od 21.10.2026.** Gotovo kad raspored radi 7 dana bez prekida.
3. CAMS i ERA5 arhiva, izmjerena greška perzistencije
4. Model koji pobjeđuje perzistenciju, posebno na danima promjene
5. Telegram bot i deploy (3 večeri zaredom bez intervencije)
6. Prva prognoza stvarnim korisnicima (cilj 15.12.)
7. Sezona uživo uz dashboard tačnosti
8. Objava rezultata

Faza 2 je najvažnija: propušteni podaci se ne mogu vratiti.
