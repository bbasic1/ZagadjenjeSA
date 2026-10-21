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
CAMS od 01.01.2013 do 22.10.2026. CAMS je izglađen i ne vidi vrhove u kotlini, pa je ovo mjera dinamike, ne prave greške na stanici.
Iste CAMS ćelije (identičan niz): bjelave = vijecnica, ilidza = saraj_polje.

### PM10

|   horizon | station     |     n |   n_promjena |   MAE_persistence |   RMSE_persistence |   bias_persistence |   MAE_persistence_promjena |
|----------:|:------------|------:|-------------:|------------------:|-------------------:|-------------------:|---------------------------:|
|         1 | SVE         | 17208 |         4089 |               8.6 |               12.1 |               -0.0 |                       19.5 |
|         1 | bjelave     |  1912 |          431 |               8.3 |               11.4 |               -0.0 |                       18.8 |
|         1 | hadzici     |  1912 |          460 |               8.6 |               12.0 |               -0.0 |                       19.2 |
|         1 | ilidza      |  1912 |          513 |               9.5 |               13.4 |               -0.1 |                       20.6 |
|         1 | ilijas      |  1912 |          506 |               9.2 |               12.6 |               -0.0 |                       19.4 |
|         1 | ivan_sedlo  |  1912 |          268 |               6.2 |                8.4 |               -0.0 |                       16.5 |
|         1 | otoka       |  1912 |          497 |               9.3 |               13.1 |               -0.0 |                       20.4 |
|         1 | saraj_polje |  1912 |          513 |               9.5 |               13.4 |               -0.1 |                       20.6 |
|         1 | vijecnica   |  1912 |          431 |               8.3 |               11.4 |               -0.0 |                       18.8 |
|         1 | vogosca     |  1912 |          470 |               8.8 |               12.2 |               -0.0 |                       19.5 |
|         2 | SVE         | 17073 |         6322 |              10.6 |               14.5 |               -0.1 |                       19.7 |
|         2 | bjelave     |  1897 |          662 |              10.1 |               13.7 |               -0.1 |                       19.1 |
|         2 | hadzici     |  1897 |          720 |              10.7 |               14.7 |               -0.1 |                       19.7 |
|         2 | ilidza      |  1897 |          772 |              11.6 |               16.0 |               -0.1 |                       20.7 |
|         2 | ilijas      |  1897 |          759 |              11.2 |               15.3 |               -0.1 |                       20.0 |
|         2 | ivan_sedlo  |  1897 |          500 |               7.8 |               10.4 |               -0.1 |                       16.6 |
|         2 | otoka       |  1897 |          739 |              11.3 |               15.7 |               -0.1 |                       20.6 |
|         2 | saraj_polje |  1897 |          772 |              11.6 |               16.0 |               -0.1 |                       20.7 |
|         2 | vijecnica   |  1897 |          662 |              10.1 |               13.7 |               -0.1 |                       19.1 |
|         2 | vogosca     |  1897 |          736 |              10.8 |               14.7 |               -0.1 |                       19.4 |

### PM2_5

|   horizon | station     |     n |   n_promjena |   MAE_persistence |   RMSE_persistence |   bias_persistence |   MAE_persistence_promjena |
|----------:|:------------|------:|-------------:|------------------:|-------------------:|-------------------:|---------------------------:|
|         1 | SVE         | 17208 |         2832 |               7.0 |               10.0 |               -0.0 |                       18.5 |
|         1 | bjelave     |  1912 |          295 |               6.8 |                9.4 |               -0.0 |                       17.5 |
|         1 | hadzici     |  1912 |          303 |               7.1 |               10.0 |               -0.0 |                       19.0 |
|         1 | ilidza      |  1912 |          374 |               7.9 |               11.4 |               -0.0 |                       19.8 |
|         1 | ilijas      |  1912 |          351 |               7.4 |               10.2 |               -0.0 |                       17.9 |
|         1 | ivan_sedlo  |  1912 |          159 |               4.9 |                6.7 |               -0.0 |                       15.6 |
|         1 | otoka       |  1912 |          359 |               7.7 |               11.2 |               -0.0 |                       19.8 |
|         1 | saraj_polje |  1912 |          374 |               7.9 |               11.4 |               -0.0 |                       19.8 |
|         1 | vijecnica   |  1912 |          295 |               6.8 |                9.4 |               -0.0 |                       17.5 |
|         1 | vogosca     |  1912 |          322 |               7.0 |                9.8 |               -0.0 |                       17.8 |
|         2 | SVE         | 17073 |         4921 |               8.6 |               12.1 |               -0.1 |                       18.2 |
|         2 | bjelave     |  1897 |          519 |               8.3 |               11.3 |               -0.1 |                       17.3 |
|         2 | hadzici     |  1897 |          576 |               8.8 |               12.3 |               -0.1 |                       18.1 |
|         2 | ilidza      |  1897 |          616 |               9.6 |               13.7 |               -0.1 |                       19.5 |
|         2 | ilijas      |  1897 |          588 |               9.0 |               12.4 |               -0.0 |                       18.1 |
|         2 | ivan_sedlo  |  1897 |          334 |               6.2 |                8.3 |               -0.0 |                       15.3 |
|         2 | otoka       |  1897 |          592 |               9.3 |               13.3 |               -0.1 |                       19.3 |
|         2 | saraj_polje |  1897 |          616 |               9.6 |               13.7 |               -0.1 |                       19.5 |
|         2 | vijecnica   |  1897 |          519 |               8.3 |               11.3 |               -0.1 |                       17.3 |
|         2 | vogosca     |  1897 |          561 |               8.6 |               11.8 |               -0.1 |                       17.5 |
