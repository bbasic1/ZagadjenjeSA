# CLAUDE.md

Prognoza zagađenja zraka u Sarajevu 24 i 48 h unaprijed, po stanici. Telegram bot svako veče šalje prognozu, a javni dashboard prati tačnost uživo. Cilj je pobijediti perzistenciju ("sutra kao danas") i imati jak CV projekat sa stvarnom evaluacijom.

Komuniciraj na bosanskom. Kod piši u Pythonu, a odluke objasni kratko.

## Najvažnije pravilo: bez curenja podataka

- Varijable koje gledaju unaprijed (padavine, vjetar, temperatura, inverzija za t+h) smiju doći **samo iz prognoze**, nikad iz mjerenja ili reanalize za taj period.
- Za trening koristi prognozu koja je bila dostupna u trenutku izdavanja. Historijske prognoze dolaze iz Open-Meteo Previous Runs arhive s leadom 2 dana za D+1 i 3 dana za D+2 (konzervativno: nijedan run nije mlađi od 18:00 dana izdavanja). Ako se ikad trenira na reanalizi (ERA5), u evaluaciji obavezno napiši da je rezultat optimističan.
- Prognoza se izdaje u **18:00 lokalno**; lag varijable PM-a smiju koristiti samo sate zaključno sa 17:00 tog dana.
- Kad je CAMS target, CAMS za ciljni dan ne smije biti feature (arhiva su analize, ne prognoze).
- Validacija je isključivo klizeća po vremenu (trening uvijek prije testa). Nikad nasumična podjela.
- **Završni test je sezona 2026/27 uživo**: svaka poslana prognoza se snima prije nego što je mjerenje poznato. Zime 2024/25 i 2025/26 su razvojni test; na njima ne podešavati hiperparametre do besvijesti.

Ako primijetiš kod koji krši ovo, zaustavi se i reci to prije nego nastaviš.

## Model i evaluacija

- **Target (odlučeno 21.10.2026):** glavni je dnevni prosjek **PM10** po stanici (mjere ga sve stanice), sekundarni PM2.5 (Bjelave, Otoka, Ilidža, Vogošća, Hadžići), poseban model.
- **Model:** LightGBM, kvantilna regresija (0.1, 0.5, 0.9), poseban model za D+1 i D+2 (direktna prognoza), na log skali. Kod: `train_v1.py`.
- **Hladan start:** pretreniranje na CAMS arhivi (target = CAMS dnevni prosjek po ćeliji), pa kalibracija na FHMZ stanicama (model output statistics).
- **Varijable:** perzistencija (zadnja 24 h, 6 h, zadnji sat, 72 h prosjek i max, trend), inverzija (prognozirana temperatura vrha Bjelašnice minus kotlina, jer 850 hPa ne postoji u arhivi prognoza), vjetar, padavine, vlažnost, pritisak, stepen grijanja (ispod 15 °C), sezonalnost, stanica. Visina graničnog sloja nije u arhivi prognoza.
- **Baselineovi:** perzistencija (glavni), klimatologija, sirovi CAMS.
- **Metrike:** MAE (µg/m³), skill prema perzistenciji, MAE na danima promjene (pomak ≥10 µg/m³), tačnost kategorije, pokrivenost intervala 0.1–0.9 (cilj 80 %).
- **Rezultat v1** (`reports/model_v1.md`, cilj CAMS): PM10 D+1 MAE 8.3 naspram 11.9 za perzistenciju, D+2 9.2 naspram 13.8; pokrivenost sirovog intervala ~65 %, preuzak; zato se širi CQR korekcijom (`conformal.py`, `reports/conformal.md`): na zimi 2025/26, uz korekciju iz 2024/25, pokrivenost je 81–84 %. Korekcija se računa samo iz prethodne zime i samo širi raspon. Na stanicama treba ponovo provjeriti kad se skupe parovi.
- **Fallback:** ako model ili podaci zakažu, šalje se perzistencija.
- Kategorije u poruci prate skalu indeksa kvaliteta zraka FHMZ (`categories.py`, PM10: odličan ≤15, dobar ≤45, umjeren ≤120, zagađen ≤195, vrlo zagađen ≤270). FHMZ je primjenjuje na satne vrijednosti, mi na dnevni prosjek. Poruka uvijek nosi ogradu da bot nije zvaničan izvor.

## Struktura repoa

| Putanja | Šta je |
| --- | --- |
| `collect.py` | Prikupljanje: FHMZ mjerenja + snimci Open-Meteo prognoze (meteo i CAMS PM) |
| `fetch_cams_archive.py` | CAMS arhiva 2013–danas → `data/cams/archive.csv.gz` |
| `fetch_meteo_archive.py` | Arhiva meteo prognoza (Previous Runs, 2023–danas) → `data/meteo/previous_runs.csv.gz` |
| `baseline.py` | Greška perzistencije i sirovog CAMS-a → `reports/baseline.md` |
| `train_v1.py` | Validacija modela → `reports/model_v1.md`; `--final` snima modele u `models/` |
| `conformal.py` | CQR korekcija raspona 10–90 % → `reports/conformal.md`; `--final` snima `models/conformal.json` |
| `forecast.py` | Večernja prognoza, poruka u Telegram, snimak u `data/predictions/` (`--dry` samo ispiše) |
| `dashboard.py` | Javni dashboard tačnosti: `data/predictions` naspram FHMZ → `site/` (GitHub Pages, ne commituje se) |
| `categories.py` | Skala kategorija indeksa kvaliteta zraka FHMZ (PM10, PM2.5) |
| `send_telegram.py` | Slanje u kanal; `--test` šalje probnu poruku |
| `data/fhmz/YYYY-MM.csv` | Satna mjerenja, long: `station,pollutant,time_utc,value,fetched_at`, bez duplikata |
| `data/forecast/YYYY-MM-DD_00\|12.csv` | Snimci prognoze dvaput dnevno: `issued_utc,station,valid_utc,` meteo, `cams_pm10,cams_pm2_5` |
| `data/predictions/YYYY-MM-DD.csv` | Svaka poslana prognoza, za praćenje tačnosti |

GitHub Actions (`.github/workflows/`):

| Workflow | Kada |
| --- | --- |
| `collect.yml` | Svaki sat (minuta 17, UTC); GitHub često preskače runove, zato tako često |
| `forecast.yml` | 16:20 i 17:20 UTC; šalje jednom dnevno, poslije 18:00 lokalno. Ručni run po defaultu ne šalje |
| `cams_archive.yml`, `meteo_archive.yml` | Ručno ili kad se promijeni skripta |
| `dashboard.yml` | Ujutro 05:40 UTC i poslije večernje prognoze; objavljuje GitHub Pages |
| `telegram_test.yml` | Ručno, probna poruka |

Secreti: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` (@kanal, bot je admin). Svi workflowi commituju kao `air-bot`.

Pokretanje lokalno: `pip install -r requirements.txt && python collect.py`.

## Činjenice o podacima

- Sva vremena u fajlovima su **UTC**. FHMZ prikazuje lokalno vrijeme (Europe/Sarajevo), `collect.py` ga pretvara.
- `collect.py` čita stranice pojedinih stanica (`amsXxx.php`), koje daju zadnjih ~7 dana, pa se propušten run sam popuni. Glavna AQI stranica se **ne koristi** jer gubi prazne ćelije.
- Stanice: vijecnica, bjelave, otoka, saraj_polje, ilidza, vogosca, hadzici, ilijas, ivan_sedlo. Ivan Sedlo je planinska stanica iznad kotline.
- U CAMS-u su Bjelave i Vijećnica ista ćelija, kao i Ilidža i Saraj Polje; model ih tretira kao jednu lokaciju dok kalibracija na stanicama ne napravi razliku.
- CAMS u oktobru 2026 precjenjuje stanice za ~9 µg/m³ PM10.
- FHMZ podaci imaju rupe (18. i 19.10.2026 fale za sve stanice; Hadžići skoro ne šalju od 17.10.). Nedostajuće vrijednosti rješavaj eksplicitno, nikad tiho.
- `issued_utc` u snimcima prognoze je vrijeme preuzimanja, ne inicijalizacije modela. Snimak počinje od 00 UTC tekućeg dana, pa sati prije `issued_utc` nisu prava prognoza.
- Open-Meteo besplatni limit broji lokacije × dane × varijable/10: sve varijable šalji u jednom zahtjevu, inače satni limit koči satima.
- Claude cloud okruženje nema pristup Open-Meteo; podaci se vuku kroz GitHub Actions.
- Ne arhiviraj WAQI/aqicn podatke (licenca zabranjuje). Open-Meteo je CC BY 4.0, uz atribuciju.

## Rad na kodu

- Ne mijenjaj format postojećih CSV fajlova bez dogovora; arhiva se ne može ponovo prikupiti.
- Greške ne gutaj tiho: jedna stanica smije pasti bez rušenja ostalih, ali neuspjeh mora biti vidljiv (log i izlazni kod 1).
- Kad se promijeni skup features ili arhiva, ponovo istreniraj `models/` (`python train_v1.py --final`, pa `python conformal.py --final`) i probaj `forecast.py --dry` prije spajanja.
- Za scraper dodaj testove koji provjeravaju format stranice, jer FHMZ može promijeniti HTML.

## Faze

1. Validacija potražnje (landing stranica, 50 prijava) — nije rađena, opcionalna
2. Prikupljanje — u toku od 21.10.2026; gotovo kad raspored radi 7 dana bez prekida (~28.10.)
3. CAMS arhiva i greška perzistencije — **gotovo** (`reports/baseline.md`)
4. Model koji pobjeđuje perzistenciju — **v1 gotov**; ostaje kalibracija na stanicama i širi interval
5. Telegram bot i deploy — uključen 21.10.2026; gotovo kad 3 večeri zaredom prođu bez intervencije
6. Prva prognoza stvarnim korisnicima — **rok sredina novembra 2026**
7. Sezona uživo uz dashboard tačnosti
8. Objava rezultata

Faza 2 je najvažnija: propušteni podaci se ne mogu vratiti.
