# Kalibracija raspona 10–90 % (CQR)

Korekcija za svaku test zimu je izračunata samo iz prognoza za prethodnu zimu, koje je napravio model treniran prije nje. Zima 2023/24 ima model treniran na samo 9 mjeseci (meteo arhiva počinje 2023), pa njena korekcija za 2024/25 previše raširi raspon; mjerodavan je red 2025/26. Cilj pokrivenosti 80 %, po 10 % sa svake strane. Target je CAMS dnevni prosjek (kao u model_v1), pa pokrivenost na FHMZ stanicama treba mjeriti posebno (dashboard).

`c_lo`, `c_hi` su pomaci na log skali: 0.10 znači da se granica pomjeri ~10 % prema van; negativni pomaci (suženje) se postavljaju na 0. Interval score = širina + 10 × promašaj; manje je bolje.

## PM10, D+1

| test    | kalibracija   |    n |   c_lo |   c_hi |   pokr_%_prije |   sirina_prije |   int_score_prije |   pokr_%_poslije |   ispod_%_poslije |   iznad_%_poslije |   sirina_poslije |   int_score_poslije |
|:--------|:--------------|-----:|-------:|-------:|---------------:|---------------:|------------------:|-----------------:|------------------:|------------------:|-----------------:|--------------------:|
| 2024/25 | 2023/24       | 1267 |   0.12 |   0.28 |          66.46 |          20.40 |             44.46 |            90.37 |              5.05 |              4.58 |            36.80 |               41.71 |
| 2025/26 | 2024/25       | 1267 |   0.05 |   0.14 |          66.30 |          18.67 |             40.27 |            83.03 |              6.00 |             10.97 |            26.24 |               35.46 |

Operativna korekcija (iz 2025/26, n = 1267): c_lo 0.000, c_hi 0.162

## PM10, D+2

| test    | kalibracija   |    n |   c_lo |   c_hi |   pokr_%_prije |   sirina_prije |   int_score_prije |   pokr_%_poslije |   ispod_%_poslije |   iznad_%_poslije |   sirina_poslije |   int_score_poslije |
|:--------|:--------------|-----:|-------:|-------:|---------------:|---------------:|------------------:|-----------------:|------------------:|------------------:|-----------------:|--------------------:|
| 2024/25 | 2023/24       | 1260 |   0.06 |   0.34 |          65.40 |          21.57 |             50.86 |            84.92 |             10.40 |              4.68 |            39.90 |               46.23 |
| 2025/26 | 2024/25       | 1260 |   0.07 |   0.19 |          61.35 |          19.98 |             47.57 |            82.70 |              5.71 |             11.59 |            29.92 |               39.00 |

Operativna korekcija (iz 2025/26, n = 1260): c_lo 0.000, c_hi 0.213

## PM2.5, D+1

| test    | kalibracija   |    n |   c_lo |   c_hi |   pokr_%_prije |   sirina_prije |   int_score_prije |   pokr_%_poslije |   ispod_%_poslije |   iznad_%_poslije |   sirina_poslije |   int_score_poslije |
|:--------|:--------------|-----:|-------:|-------:|---------------:|---------------:|------------------:|-----------------:|------------------:|------------------:|-----------------:|--------------------:|
| 2024/25 | 2023/24       | 1267 |   0.11 |   0.22 |          69.85 |          19.05 |             39.86 |            88.16 |              5.05 |              6.79 |            31.09 |               36.74 |
| 2025/26 | 2024/25       | 1267 |   0.03 |   0.15 |          68.67 |          17.68 |             36.34 |            83.66 |              6.55 |              9.79 |            24.64 |               32.48 |

Operativna korekcija (iz 2025/26, n = 1267): c_lo 0.000, c_hi 0.149

## PM2.5, D+2

| test    | kalibracija   |    n |   c_lo |   c_hi |   pokr_%_prije |   sirina_prije |   int_score_prije |   pokr_%_poslije |   ispod_%_poslije |   iznad_%_poslije |   sirina_poslije |   int_score_poslije |
|:--------|:--------------|-----:|-------:|-------:|---------------:|---------------:|------------------:|-----------------:|------------------:|------------------:|-----------------:|--------------------:|
| 2024/25 | 2023/24       | 1260 |   0.13 |   0.37 |          61.98 |          18.76 |             46.57 |            90.63 |              6.27 |              3.10 |            38.36 |               41.64 |
| 2025/26 | 2024/25       | 1260 |   0.06 |   0.19 |          62.78 |          17.93 |             42.87 |            81.03 |              6.67 |             12.30 |            26.91 |               35.34 |

Operativna korekcija (iz 2025/26, n = 1260): c_lo 0.000, c_hi 0.217
