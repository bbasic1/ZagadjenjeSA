# Faza 3: baseline greška
Izdavanje u 18:00 lokalno, target je dnevni prosjek za D+1 i D+2. Dan valjan uz ≥18 sati. Dan promjene: dnevni prosjek se pomjeri ≥10 µg/m³ u odnosu na dan izdavanja. Sve greške u µg/m³.

## PM10: FHMZ mjerenja (dani izdavanja 15.10.2026 do 15.10.2026)
Malo dana, brojke su orijentacione dok se ne skupi sezona.

|   horizon | station     |   n |   n_promjena |   MAE_persistence |   RMSE_persistence |   bias_persistence |   MAE_persistence_promjena |   MAE_cams |   RMSE_cams |   bias_cams |   MAE_cams_promjena |
|----------:|:------------|----:|-------------:|------------------:|-------------------:|-------------------:|---------------------------:|-----------:|------------:|------------:|--------------------:|
|         1 | SVE         |   8 |            0 |               2.9 |                3.1 |               -1.0 |                        nan |       10.2 |        11.3 |         8.8 |                 nan |
|         1 | bjelave     |   1 |            0 |               0.9 |                0.9 |                0.9 |                        nan |       12.1 |        12.1 |        12.1 |                 nan |
|         1 | ilidza      |   1 |            0 |               4.1 |                4.1 |               -4.1 |                        nan |       17.8 |        17.8 |        17.8 |                 nan |
|         1 | ilijas      |   1 |            0 |               3.0 |                3.0 |                3.0 |                        nan |        5.7 |         5.7 |        -5.7 |                 nan |
|         1 | ivan_sedlo  |   1 |            0 |               2.5 |                2.5 |               -2.5 |                        nan |        7.9 |         7.9 |         7.9 |                 nan |
|         1 | otoka       |   1 |            0 |               3.1 |                3.1 |               -3.1 |                        nan |       10.6 |        10.6 |        10.6 |                 nan |
|         1 | saraj_polje |   1 |            0 |               4.1 |                4.1 |               -4.1 |                        nan |       12.3 |        12.3 |        12.3 |                 nan |
|         1 | vijecnica   |   1 |            0 |               3.6 |                3.6 |                3.6 |                        nan |       14.2 |        14.2 |        14.2 |                 nan |
|         1 | vogosca     |   1 |            0 |               1.9 |                1.9 |               -1.9 |                        nan |        1.0 |         1.0 |         1.0 |                 nan |

## PM2_5: FHMZ mjerenja (dani izdavanja 15.10.2026 do 15.10.2026)
Malo dana, brojke su orijentacione dok se ne skupi sezona.

|   horizon | station   |   n |   n_promjena |   MAE_persistence |   RMSE_persistence |   bias_persistence |   MAE_persistence_promjena |   MAE_cams |   RMSE_cams |   bias_cams |   MAE_cams_promjena |
|----------:|:----------|----:|-------------:|------------------:|-------------------:|-------------------:|---------------------------:|-----------:|------------:|------------:|--------------------:|
|         1 | SVE       |   5 |            0 |               2.1 |                2.7 |               -2.0 |                        nan |       10.9 |        12.2 |        10.9 |                 nan |
|         1 | bjelave   |   1 |            0 |               0.3 |                0.3 |                0.3 |                        nan |       12.6 |        12.6 |        12.6 |                 nan |
|         1 | hadzici   |   1 |            0 |               0.1 |                0.1 |               -0.1 |                        nan |       10.3 |        10.3 |        10.3 |                 nan |
|         1 | ilidza    |   1 |            0 |               4.3 |                4.3 |               -4.3 |                        nan |       18.0 |        18.0 |        18.0 |                 nan |
|         1 | otoka     |   1 |            0 |               3.2 |                3.2 |               -3.2 |                        nan |       12.2 |        12.2 |        12.2 |                 nan |
|         1 | vogosca   |   1 |            0 |               2.6 |                2.6 |               -2.6 |                        nan |        1.2 |         1.2 |         1.2 |                 nan |

## Perzistencija na CAMS arhivi (sezona grijanja, okt–mar)
CAMS od 01.01.2013 do 21.10.2026. CAMS je izglađen i ne vidi vrhove u kotlini, pa je ovo mjera dinamike, ne prave greške na stanici.
Iste CAMS ćelije (identičan niz): bjelave = vijecnica, ilidza = saraj_polje.

### PM10

|   horizon | station     |     n |   n_promjena |   MAE_persistence |   RMSE_persistence |   bias_persistence |   MAE_persistence_promjena |
|----------:|:------------|------:|-------------:|------------------:|-------------------:|-------------------:|---------------------------:|
|         1 | SVE         | 22167 |         5656 |               9.1 |               12.9 |               -0.1 |                       20.2 |
|         1 | bjelave     |  2463 |          605 |               8.7 |               12.1 |               -0.1 |                       19.2 |
|         1 | hadzici     |  2463 |          644 |               9.1 |               12.8 |               -0.1 |                       19.8 |
|         1 | ilidza      |  2463 |          715 |              10.2 |               14.6 |               -0.1 |                       21.7 |
|         1 | ilijas      |  2463 |          689 |               9.6 |               13.3 |               -0.1 |                       20.1 |
|         1 | ivan_sedlo  |  2463 |          350 |               6.3 |                8.9 |               -0.0 |                       17.5 |
|         1 | otoka       |  2463 |          698 |              10.0 |               14.3 |               -0.1 |                       21.5 |
|         1 | saraj_polje |  2463 |          715 |              10.2 |               14.6 |               -0.1 |                       21.7 |
|         1 | vijecnica   |  2463 |          605 |               8.7 |               12.1 |               -0.1 |                       19.2 |
|         1 | vogosca     |  2463 |          635 |               9.0 |               12.5 |               -0.1 |                       19.6 |
|         2 | SVE         | 22032 |         8517 |              11.2 |               15.6 |               -0.1 |                       20.4 |
|         2 | bjelave     |  2448 |          894 |              10.6 |               14.5 |               -0.1 |                       19.6 |
|         2 | hadzici     |  2448 |          968 |              11.3 |               15.6 |               -0.1 |                       20.4 |
|         2 | ilidza      |  2448 |         1051 |              12.4 |               17.4 |               -0.1 |                       21.6 |
|         2 | ilijas      |  2448 |         1024 |              11.8 |               16.2 |               -0.1 |                       20.7 |
|         2 | ivan_sedlo  |  2448 |          645 |               7.9 |               11.2 |               -0.1 |                       17.2 |
|         2 | otoka       |  2448 |         1013 |              12.1 |               17.1 |               -0.1 |                       21.6 |
|         2 | saraj_polje |  2448 |         1051 |              12.4 |               17.4 |               -0.1 |                       21.6 |
|         2 | vijecnica   |  2448 |          894 |              10.6 |               14.5 |               -0.1 |                       19.6 |
|         2 | vogosca     |  2448 |          977 |              11.2 |               15.2 |               -0.1 |                       19.7 |

### PM2_5

|   horizon | station     |     n |   n_promjena |   MAE_persistence |   RMSE_persistence |   bias_persistence |   MAE_persistence_promjena |
|----------:|:------------|------:|-------------:|------------------:|-------------------:|-------------------:|---------------------------:|
|         1 | SVE         | 22167 |         3966 |               7.3 |               10.5 |               -0.0 |                       18.8 |
|         1 | bjelave     |  2463 |          410 |               7.0 |                9.8 |               -0.0 |                       18.0 |
|         1 | hadzici     |  2463 |          447 |               7.4 |               10.5 |               -0.0 |                       19.0 |
|         1 | ilidza      |  2463 |          525 |               8.3 |               12.0 |               -0.0 |                       20.1 |
|         1 | ilijas      |  2463 |          483 |               7.6 |               10.6 |               -0.0 |                       18.3 |
|         1 | ivan_sedlo  |  2463 |          218 |               5.0 |                7.0 |               -0.0 |                       16.3 |
|         1 | otoka       |  2463 |          511 |               8.1 |               11.8 |               -0.0 |                       20.1 |
|         1 | saraj_polje |  2463 |          525 |               8.3 |               12.0 |               -0.0 |                       20.1 |
|         1 | vijecnica   |  2463 |          410 |               7.0 |                9.8 |               -0.0 |                       18.0 |
|         1 | vogosca     |  2463 |          437 |               7.2 |                9.9 |               -0.0 |                       17.7 |
|         2 | SVE         | 22032 |         6627 |               9.0 |               12.6 |               -0.1 |                       18.5 |
|         2 | bjelave     |  2448 |          699 |               8.5 |               11.7 |               -0.1 |                       17.5 |
|         2 | hadzici     |  2448 |          772 |               9.1 |               12.8 |               -0.1 |                       18.4 |
|         2 | ilidza      |  2448 |          831 |              10.0 |               14.2 |               -0.1 |                       19.8 |
|         2 | ilijas      |  2448 |          791 |               9.4 |               12.9 |               -0.1 |                       18.5 |
|         2 | ivan_sedlo  |  2448 |          444 |               6.3 |                8.9 |               -0.0 |                       15.9 |
|         2 | otoka       |  2448 |          808 |               9.8 |               14.0 |               -0.1 |                       19.6 |
|         2 | saraj_polje |  2448 |          831 |              10.0 |               14.2 |               -0.1 |                       19.8 |
|         2 | vijecnica   |  2448 |          699 |               8.5 |               11.7 |               -0.1 |                       17.5 |
|         2 | vogosca     |  2448 |          752 |               8.8 |               11.9 |               -0.1 |                       17.5 |
