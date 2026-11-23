# Prueba de carga del servicio de predicción

Generado el 2026-11-18 18:20 con `python -m carga.resumen` a partir de los archivos de `reports/carga/`. Objetivo de servicio: p95 de hasta 500 ms, errores de hasta 1.0 % y al menos 90 % de la carga ofrecida atendida. Cada usuario simulado intenta una tarea por segundo, así que los usuarios de un escalón son también las peticiones por segundo que se le ofrecen al servicio. Las corridas cuyo nombre termina en `_r` y un número son repeticiones de la corrida del mismo nombre.

## Resumen por configuración

Cada fila junta una corrida con sus repeticiones y da el menor y el mayor valor de cada medida entre ellas.

| Corrida | Configuración | Estaciones por lote | Corridas | Punto de degradación | Capacidad dentro del objetivo (peticiones/s) | Mediana de la capacidad | Predicciones/s en ese escalón | p95 en ese escalón (ms) | Rendimiento máximo (peticiones/s) | Errores en el último escalón | Arranque del servicio (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `un_proceso` | 1 proceso, 1 CPU | 3 | 5 | 10 a 20 usuarios | 8.0 a 15.0 | 10.0 | 12.1 a 23.2 | 77 a 458 | 14.6 a 27.7 | 0.0 a 88.1 % | 8.5 a 42.7 |
| `un_proceso_en_serie` | 1 proceso, 1 CPU, 1 petición a la vez por proceso | 3 | 4 | 30 a 60 usuarios | 20.0 a 30.0 | 30.0 | 29.2 a 46.0 | 108 a 313 | 43.9 a 54.2 | 0.0 % | 10.2 a 22.9 |
| `dos_procesos_un_cpu` | 2 procesos, 1 CPU | 3 | 2 | 15 a 20 usuarios | 10.0 a 15.1 | 12.5 | 15.1 a 23.4 | 72 a 450 | 17.4 a 19.0 | 6.5 a 99.0 % | 21.8 a 31.4 |
| `dos_procesos` | 2 procesos, 2 CPU | 3 | 3 | 15 a 60 usuarios | 10.0 a 30.0 | 15.0 | 15.1 a 46.0 | 148 a 266 | 23.1 a 30.0 | 0.0 % | 11.8 a 31.7 |
| `dos_procesos_en_serie` | 2 procesos, 2 CPU, 1 petición a la vez por proceso | 3 | 2 | 60 usuarios; ninguno en 1 | 30.0 a 60.0 | 45.0 | 46.0 a 90.4 | 102 a 391 | 59.3 a 60.0 | 0.0 % | 20.7 a 22.3 |
| `lote_hora` | 1 proceso, 1 CPU | 472 | 3 | 8 a 12 usuarios | 4.0 a 8.0 | 8.0 | 1888.0 a 3776.0 | 149 a 320 | 6.8 a 12.0 | 0.0 % | 13.3 a 30.9 |

## Resumen por corrida

| Corrida | Configuración | Estaciones por lote | Punto de degradación | Capacidad dentro del objetivo (peticiones/s) | Predicciones/s en ese escalón | p95 en ese escalón (ms) | Rendimiento máximo (peticiones/s) | Errores en el último escalón | Arranque del servicio (s) |
|---|---|---|---|---|---|---|---|---|---|
| `un_proceso` | 1 proceso, 1 CPU | 3 | 10 usuarios | 8.0 | 12.1 | 458 | 14.6 | 85.2 % | 42.73 |
| `un_proceso_r2` | 1 proceso, 1 CPU | 3 | 15 usuarios | 10.0 | 15.1 | 77 | 18.2 | 88.1 % | 27.54 |
| `un_proceso_r3` | 1 proceso, 1 CPU | 3 | 20 usuarios | 15.0 | 23.2 | 271 | 18.5 | 16.7 % | 22.75 |
| `un_proceso_r4` | 1 proceso, 1 CPU | 3 | 15 usuarios | 10.0 | 15.1 | 255 | 27.7 | 0.0 % | 17.88 |
| `un_proceso_r5` | 1 proceso, 1 CPU | 3 | 20 usuarios | 15.0 | 23.2 | 241 | 22.4 | 0.0 % | 8.53 |
| `un_proceso_en_serie` | 1 proceso, 1 CPU, 1 petición a la vez por proceso | 3 | 30 usuarios | 20.0 | 29.2 | 108 | 43.9 | 0.0 % | 18.42 |
| `un_proceso_en_serie_r2` | 1 proceso, 1 CPU, 1 petición a la vez por proceso | 3 | 60 usuarios | 30.0 | 46.0 | 228 | 54.2 | 0.0 % | 11.81 |
| `un_proceso_en_serie_r3` | 1 proceso, 1 CPU, 1 petición a la vez por proceso | 3 | 60 usuarios | 30.0 | 46.0 | 313 | 45.9 | 0.0 % | 22.92 |
| `un_proceso_en_serie_r4` | 1 proceso, 1 CPU, 1 petición a la vez por proceso | 3 | 60 usuarios | 30.0 | 46.0 | 202 | 52.1 | 0.0 % | 10.25 |
| `dos_procesos_un_cpu` | 2 procesos, 1 CPU | 3 | 15 usuarios | 10.0 | 15.1 | 72 | 17.4 | 99.0 % | 31.41 |
| `dos_procesos_un_cpu_r2` | 2 procesos, 1 CPU | 3 | 20 usuarios | 15.1 | 23.4 | 450 | 19.0 | 6.5 % | 21.83 |
| `dos_procesos` | 2 procesos, 2 CPU | 3 | 20 usuarios | 15.0 | 23.3 | 148 | 23.1 | 0.0 % | 31.1 |
| `dos_procesos_r2` | 2 procesos, 2 CPU | 3 | 15 usuarios | 10.0 | 15.1 | 182 | 26.4 | 0.0 % | 31.72 |
| `dos_procesos_r3` | 2 procesos, 2 CPU | 3 | 60 usuarios | 30.0 | 46.0 | 266 | 30.0 | 0.0 % | 11.77 |
| `dos_procesos_en_serie` | 2 procesos, 2 CPU, 1 petición a la vez por proceso | 3 | 60 usuarios | 30.0 | 46.0 | 102 | 59.3 | 0.0 % | 22.3 |
| `dos_procesos_en_serie_r2` | 2 procesos, 2 CPU, 1 petición a la vez por proceso | 3 | ninguno | 60.0 | 90.4 | 391 | 60.0 | 0.0 % | 20.74 |
| `lote_hora` | 1 proceso, 1 CPU | 472 | 8 usuarios | 4.0 | 1888.0 | 149 | 6.8 | 0.0 % | 18.98 |
| `lote_hora_r2` | 1 proceso, 1 CPU | 472 | 12 usuarios | 8.0 | 3776.0 | 320 | 8.6 | 0.0 % | 30.9 |
| `lote_hora_r3` | 1 proceso, 1 CPU | 472 | 12 usuarios | 8.0 | 3776.0 | 219 | 12.0 | 0.0 % | 13.33 |

## Diagnóstico de concurrencia

`python -m carga.correr --diagnostico` dentro de un contenedor del servicio con 1 CPU: el modelo `mibici-equipo38-p2-riesgo` versión 1 predice la petición de ejemplo sin pasar por HTTP, 8 s por medición.

| Hilos que predicen a la vez | Predicciones/s | CPU por predicción (ms) | CPU en llamadas al sistema | Periodos frenados por el límite de CPU |
|---|---|---|---|---|
| 1 | 62.5 | 16.0 | 2 % | 37 |
| 2 | 29.9 | 33.5 | 22 % | 80 |
| 4 | 16.3 | 61.5 | 29 % | 81 |
| 8 | 12.6 | 80.0 | 32 % | 86 |
| 16 | 11.8 | 84.8 | 31 % | 90 |

## Corrida `un_proceso`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 42.73 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 13:57:18.

Punto de degradación: escalón 5, 10 usuarios (p95 de 1013 ms). Capacidad dentro del objetivo: 8.0 peticiones por segundo con 8 usuarios (p95 de 458 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 89 | 172 | 179 | 191 | 0.00 % | 15 % y 62 % | 217 |
| 2 | 4 | 199 | 4.0 | 6.1 | 43 | 456 | 888 | 1154 | 0.00 % | 25 % y 69 % | 227 |
| 3 | 6 | 299 | 6.0 | 9.4 | 68 | 362 | 561 | 604 | 0.00 % | 37 % y 84 % | 218 |
| 4 | 8 | 400 | 8.0 | 12.1 | 42 | 458 | 729 | 905 | 0.00 % | 39 % y 99 % | 231 |
| 5 | 10 | 492 | 9.8 | 14.8 | 31 | 1013 (sobre el objetivo) | 1535 | 1797 | 0.00 % | 37 % y 101 % | 232 |
| 6 | 15 | 441 | 8.8 | 13.4 | 1288 | 3402 (sobre el objetivo) | 4039 | 4165 | 0.00 % | 94 % y 108 % | 235 |
| 7 | 20 | 541 | 10.8 | 15.3 | 1498 | 5004 (sobre el objetivo) | 5007 | 5165 | 8.50 % | 101 % y 103 % | 238 |
| 8 | 30 | 728 | 14.6 | 21.1 | 2003 | 3362 (sobre el objetivo) | 3541 | 4324 | 0.00 % | 101 % y 103 % | 237 |
| 9 | 60 | 582 | 11.6 | 1.5 | 5003 | 5007 (sobre el objetivo) | 5451 | 6099 | 85.22 % | 101 % y 102 % | 250 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 18 | 46 | 1.3 | 96 | 161 | 0.5 | 84 | 178 |
| 2 | 4 | 0.4 | 4 | 34 | 2.4 | 46 | 236 | 1.2 | 50 | 456 |
| 3 | 6 | 0.7 | 5 | 28 | 3.3 | 74 | 357 | 2.1 | 125 | 390 |
| 4 | 8 | 0.9 | 5 | 44 | 4.6 | 46 | 543 | 2.5 | 53 | 454 |
| 5 | 10 | 1.0 | 4 | 100 | 5.8 | 35 | 1064 | 3.0 | 30 | 961 |
| 6 | 15 | 1.0 | 26 | 396 | 5.1 | 1601 | 3566 | 2.8 | 1600 | 3600 |
| 7 | 20 | 1.1 | 53 | 5004 | 6.2 | 1555 | 5004 | 3.5 | 1560 | 5002 |
| 8 | 30 | 1.4 | 18 | 495 | 9.3 | 2033 | 3374 | 3.9 | 2123 | 3393 |
| 9 | 60 | 1.1 | 4122 | 5005 | 6.8 | 5003 | 5007 | 3.7 | 5003 | 5010 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 15.0 % | 62.3 % | 217 | 3.5 % | 48.1 % | 429 | 0.4 % | 0.6 % | 42 |
| 2 | 4 | 24.7 % | 69.4 % | 227 | 5.8 % | 82.3 % | 442 | 1.0 % | 1.2 % | 43 |
| 3 | 6 | 37.1 % | 83.9 % | 218 | 7.8 % | 64.8 % | 428 | 1.5 % | 2.5 % | 43 |
| 4 | 8 | 39.1 % | 99.5 % | 231 | 8.4 % | 46.2 % | 439 | 1.8 % | 2.4 % | 43 |
| 5 | 10 | 36.8 % | 101.2 % | 232 | 5.3 % | 51.6 % | 438 | 1.7 % | 2.6 % | 43 |
| 6 | 15 | 94.4 % | 108.4 % | 235 | 11.5 % | 105.6 % | 439 | 2.2 % | 3.1 % | 44 |
| 7 | 20 | 100.9 % | 102.6 % | 238 | 3.4 % | 46.6 % | 428 | 2.4 % | 4.0 % | 45 |
| 8 | 30 | 101.1 % | 102.8 % | 237 | 2.2 % | 15.2 % | 428 | 2.5 % | 4.1 % | 45 |
| 9 | 60 | 100.7 % | 101.8 % | 250 | 4.5 % | 57.6 % | 441 | 3.4 % | 5.4 % | 52 |

Variación frente a sus repeticiones:

| Escalón | Usuarios | Peticiones/s, `un_proceso` | Peticiones/s, `un_proceso_r2` | Peticiones/s, `un_proceso_r3` | Peticiones/s, `un_proceso_r4` | Peticiones/s, `un_proceso_r5` | p95 (ms), `un_proceso` | p95 (ms), `un_proceso_r2` | p95 (ms), `un_proceso_r3` | p95 (ms), `un_proceso_r4` | p95 (ms), `un_proceso_r5` | p95 mayor entre p95 menor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 172 | 128 | 140 | 170 | 69 | 2.5 |
| 2 | 4 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 456 | 71 | 110 | 304 | 62 | 7.3 |
| 3 | 6 | 6.0 | 6.0 | 6.0 | 6.0 | 6.0 | 362 | 110 | 120 | 68 | 50 | 7.2 |
| 4 | 8 | 8.0 | 8.0 | 8.0 | 8.0 | 8.0 | 458 | 73 | 176 | 102 | 99 | 6.3 |
| 5 | 10 | 9.8 | 10.0 | 10.0 | 10.0 | 10.0 | 1013 | 77 | 108 | 255 | 165 | 13.2 |
| 6 | 15 | 8.8 | 14.6 | 15.0 | 14.9 | 15.0 | 3402 | 894 | 271 | 1076 | 241 | 14.1 |
| 7 | 20 | 10.8 | 18.2 | 18.5 | 17.3 | 19.5 | 5004 | 1942 | 1503 | 1610 | 1254 | 4.0 |
| 8 | 30 | 14.6 | 12.6 | 15.3 | 27.7 | 22.4 | 3362 | 4634 | 2895 | 1464 | 1933 | 3.2 |
| 9 | 60 | 11.6 | 11.6 | 15.6 | 22.0 | 22.1 | 5007 | 5019 | 5002 | 3830 | 3547 | 1.4 |

## Corrida `un_proceso_r2`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 27.54 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 14:31:17.

Punto de degradación: escalón 6, 15 usuarios (p95 de 894 ms). Capacidad dentro del objetivo: 10.0 peticiones por segundo con 10 usuarios (p95 de 77 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 100 | 2.0 | 2.8 | 67 | 128 | 221 | 225 | 0.00 % | 11 % y 33 % | 227 |
| 2 | 4 | 200 | 4.0 | 6.1 | 22 | 71 | 102 | 208 | 0.00 % | 13 % y 44 % | 217 |
| 3 | 6 | 300 | 6.0 | 9.5 | 38 | 110 | 169 | 213 | 0.00 % | 17 % y 53 % | 218 |
| 4 | 8 | 400 | 8.0 | 12.2 | 37 | 73 | 107 | 134 | 0.00 % | 19 % y 42 % | 218 |
| 5 | 10 | 500 | 10.0 | 15.1 | 37 | 77 | 103 | 111 | 0.00 % | 20 % y 24 % | 218 |
| 6 | 15 | 732 | 14.6 | 22.8 | 19 | 894 (sobre el objetivo) | 1600 | 2076 | 0.00 % | 35 % y 102 % | 222 |
| 7 | 20 | 910 | 18.2 | 26.3 | 369 | 1942 (sobre el objetivo) | 2910 | 5015 | 0.88 % | 78 % y 102 % | 233 |
| 8 | 30 | 632 | 12.6 | 18.3 | 2238 | 4634 (sobre el objetivo) | 5561 | 6139 | 3.32 % | 101 % y 103 % | 233 |
| 9 | 60 | 578 | 11.6 | 0.3 | 5004 | 5019 (sobre el objetivo) | 5429 | 5654 | 88.06 % | 101 % y 103 % | 250 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 17 | 30 | 1.3 | 70 | 133 | 0.5 | 71 | 124 |
| 2 | 4 | 0.4 | 4 | 22 | 2.4 | 25 | 88 | 1.2 | 24 | 54 |
| 3 | 6 | 0.7 | 10 | 25 | 3.3 | 40 | 110 | 2.1 | 42 | 117 |
| 4 | 8 | 0.9 | 8 | 17 | 4.6 | 37 | 77 | 2.5 | 39 | 76 |
| 5 | 10 | 1.0 | 10 | 18 | 5.9 | 37 | 79 | 3.1 | 38 | 82 |
| 6 | 15 | 1.4 | 3 | 122 | 8.4 | 20 | 858 | 4.8 | 20 | 1182 |
| 7 | 20 | 1.8 | 18 | 297 | 11.4 | 448 | 1962 | 5.1 | 540 | 2059 |
| 8 | 30 | 1.3 | 12 | 41 | 7.5 | 2403 | 4680 | 3.9 | 2414 | 4863 |
| 9 | 60 | 1.4 | 3963 | 5005 | 6.5 | 5004 | 5018 | 3.6 | 5004 | 5032 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 10.8 % | 33.0 % | 227 | 2.9 % | 39.9 % | 431 | 0.4 % | 0.6 % | 42 |
| 2 | 4 | 13.0 % | 44.2 % | 217 | 1.8 % | 23.5 % | 432 | 0.6 % | 0.7 % | 43 |
| 3 | 6 | 17.4 % | 53.4 % | 218 | 0.2 % | 0.3 % | 431 | 0.8 % | 1.2 % | 43 |
| 4 | 8 | 18.9 % | 42.2 % | 218 | 0.7 % | 8.0 % | 440 | 1.0 % | 1.6 % | 43 |
| 5 | 10 | 19.9 % | 23.7 % | 218 | 2.3 % | 24.1 % | 440 | 1.2 % | 1.5 % | 43 |
| 6 | 15 | 35.0 % | 102.2 % | 222 | 1.7 % | 23.9 % | 432 | 1.9 % | 3.0 % | 44 |
| 7 | 20 | 78.1 % | 101.8 % | 233 | 0.7 % | 7.1 % | 431 | 2.7 % | 3.9 % | 44 |
| 8 | 30 | 101.2 % | 103.3 % | 233 | 1.6 % | 19.9 % | 442 | 2.6 % | 3.5 % | 46 |
| 9 | 60 | 100.9 % | 102.9 % | 250 | 0.2 % | 0.4 % | 431 | 3.4 % | 6.2 % | 52 |

## Corrida `un_proceso_r3`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 22.75 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 15:06:06.

Punto de degradación: escalón 7, 20 usuarios (p95 de 1503 ms). Capacidad dentro del objetivo: 15.0 peticiones por segundo con 15 usuarios (p95 de 271 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 48 | 140 | 183 | 186 | 0.00 % | 11 % y 51 % | 218 |
| 2 | 4 | 198 | 4.0 | 6.0 | 21 | 110 | 1139 | 1174 | 0.00 % | 14 % y 56 % | 218 |
| 3 | 6 | 300 | 6.0 | 9.5 | 22 | 120 | 591 | 781 | 0.00 % | 16 % y 39 % | 222 |
| 4 | 8 | 400 | 8.0 | 12.2 | 50 | 176 | 497 | 795 | 0.00 % | 28 % y 94 % | 232 |
| 5 | 10 | 500 | 10.0 | 15.1 | 37 | 108 | 142 | 234 | 0.00 % | 23 % y 43 % | 220 |
| 6 | 15 | 750 | 15.0 | 23.2 | 65 | 271 | 615 | 826 | 0.00 % | 44 % y 80 % | 230 |
| 7 | 20 | 924 | 18.5 | 27.1 | 393 | 1503 (sobre el objetivo) | 1790 | 2301 | 0.00 % | 84 % y 102 % | 228 |
| 8 | 30 | 765 | 15.3 | 23.2 | 1882 | 2895 (sobre el objetivo) | 3706 | 4484 | 0.00 % | 101 % y 103 % | 240 |
| 9 | 60 | 779 | 15.6 | 19.2 | 3913 | 5002 (sobre el objetivo) | 5004 | 5014 | 16.69 % | 101 % y 104 % | 245 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 14 | 20 | 1.3 | 52 | 146 | 0.5 | 51 | 103 |
| 2 | 4 | 0.4 | 3 | 17 | 2.4 | 22 | 120 | 1.2 | 22 | 110 |
| 3 | 6 | 0.7 | 3 | 21 | 3.3 | 23 | 248 | 2.1 | 24 | 96 |
| 4 | 8 | 0.9 | 12 | 25 | 4.6 | 56 | 205 | 2.5 | 54 | 158 |
| 5 | 10 | 1.0 | 9 | 17 | 5.9 | 38 | 115 | 3.1 | 40 | 101 |
| 6 | 15 | 1.5 | 13 | 38 | 8.6 | 76 | 275 | 4.9 | 94 | 354 |
| 7 | 20 | 1.8 | 78 | 271 | 11.5 | 692 | 1499 | 5.2 | 613 | 1598 |
| 8 | 30 | 1.5 | 9 | 207 | 9.1 | 1952 | 3104 | 4.7 | 1902 | 2974 |
| 9 | 60 | 1.6 | 1301 | 2026 | 9.2 | 4075 | 5002 | 4.8 | 4122 | 5003 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 10.6 % | 51.5 % | 218 | 1.8 % | 25.7 % | 433 | 0.3 % | 0.5 % | 42 |
| 2 | 4 | 13.7 % | 55.7 % | 218 | 2.7 % | 37.2 % | 433 | 0.7 % | 0.8 % | 43 |
| 3 | 6 | 16.4 % | 39.4 % | 222 | 3.4 % | 37.5 % | 443 | 0.9 % | 1.4 % | 43 |
| 4 | 8 | 28.4 % | 94.0 % | 232 | 1.6 % | 21.6 % | 432 | 1.2 % | 1.6 % | 43 |
| 5 | 10 | 23.1 % | 43.4 % | 220 | 1.8 % | 23.6 % | 446 | 1.2 % | 1.5 % | 43 |
| 6 | 15 | 44.3 % | 80.4 % | 230 | 0.2 % | 0.3 % | 432 | 1.6 % | 2.6 % | 43 |
| 7 | 20 | 84.3 % | 101.8 % | 228 | 2.5 % | 35.2 % | 433 | 2.4 % | 3.4 % | 44 |
| 8 | 30 | 100.7 % | 103.4 % | 240 | 3.5 % | 32.7 % | 441 | 2.5 % | 3.2 % | 45 |
| 9 | 60 | 100.9 % | 103.6 % | 245 | 4.7 % | 34.6 % | 444 | 2.6 % | 4.6 % | 48 |

## Corrida `un_proceso_r4`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 17.88 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 16:59:22.

Punto de degradación: escalón 6, 15 usuarios (p95 de 1076 ms). Capacidad dentro del objetivo: 10.0 peticiones por segundo con 10 usuarios (p95 de 255 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 65 | 170 | 352 | 363 | 0.00 % | 13 % y 80 % | 229 |
| 2 | 4 | 200 | 4.0 | 6.1 | 44 | 304 | 1021 | 1586 | 0.00 % | 19 % y 60 % | 219 |
| 3 | 6 | 300 | 6.0 | 9.5 | 24 | 68 | 166 | 191 | 0.00 % | 20 % y 59 % | 230 |
| 4 | 8 | 400 | 8.0 | 12.1 | 23 | 102 | 439 | 485 | 0.00 % | 23 % y 86 % | 220 |
| 5 | 10 | 500 | 10.0 | 15.1 | 35 | 255 | 739 | 931 | 0.00 % | 34 % y 100 % | 223 |
| 6 | 15 | 743 | 14.9 | 23.1 | 89 | 1076 (sobre el objetivo) | 1448 | 1594 | 0.00 % | 61 % y 101 % | 236 |
| 7 | 20 | 864 | 17.3 | 25.2 | 1007 | 1610 (sobre el objetivo) | 1832 | 2186 | 0.00 % | 98 % y 106 % | 240 |
| 8 | 30 | 1,387 | 27.7 | 42.4 | 692 | 1464 (sobre el objetivo) | 3211 | 3495 | 0.00 % | 95 % y 101 % | 232 |
| 9 | 60 | 1,102 | 22.0 | 32.7 | 2515 | 3830 (sobre el objetivo) | 4217 | 4785 | 0.00 % | 100 % y 103 % | 246 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 14 | 26 | 1.3 | 78 | 172 | 0.5 | 64 | 130 |
| 2 | 4 | 0.4 | 4 | 28 | 2.4 | 51 | 390 | 1.2 | 47 | 304 |
| 3 | 6 | 0.7 | 3 | 10 | 3.3 | 25 | 71 | 2.1 | 27 | 66 |
| 4 | 8 | 0.9 | 3 | 17 | 4.6 | 25 | 126 | 2.5 | 24 | 102 |
| 5 | 10 | 1.0 | 4 | 24 | 5.9 | 44 | 351 | 3.1 | 45 | 273 |
| 6 | 15 | 1.4 | 10 | 156 | 8.6 | 100 | 1101 | 4.8 | 119 | 1057 |
| 7 | 20 | 1.7 | 153 | 320 | 10.7 | 1009 | 1608 | 4.8 | 1131 | 1663 |
| 8 | 30 | 2.9 | 210 | 578 | 16.0 | 735 | 1425 | 8.8 | 782 | 1682 |
| 9 | 60 | 2.8 | 770 | 2258 | 12.6 | 2616 | 3780 | 6.7 | 2600 | 3986 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 13.2 % | 80.0 % | 229 | 1.1 % | 11.8 % | 405 | 0.5 % | 0.8 % | 43 |
| 2 | 4 | 18.8 % | 60.3 % | 219 | 2.6 % | 33.9 % | 402 | 0.8 % | 1.2 % | 43 |
| 3 | 6 | 20.4 % | 59.1 % | 230 | 2.3 % | 23.8 % | 405 | 1.1 % | 2.0 % | 43 |
| 4 | 8 | 23.1 % | 86.3 % | 220 | 1.3 % | 17.0 % | 401 | 1.2 % | 1.6 % | 43 |
| 5 | 10 | 33.6 % | 100.1 % | 223 | 2.8 % | 37.8 % | 401 | 1.5 % | 2.0 % | 44 |
| 6 | 15 | 61.2 % | 101.3 % | 236 | 2.3 % | 31.3 % | 401 | 2.2 % | 3.0 % | 44 |
| 7 | 20 | 98.4 % | 105.6 % | 240 | 2.7 % | 38.1 % | 401 | 2.6 % | 3.2 % | 45 |
| 8 | 30 | 95.4 % | 101.1 % | 232 | 2.4 % | 33.3 % | 401 | 3.3 % | 4.0 % | 46 |
| 9 | 60 | 100.3 % | 103.2 % | 246 | 4.5 % | 36.4 % | 401 | 2.9 % | 12.9 % | 47 |

## Corrida `un_proceso_r5`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 8.53 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 17:41:47.

Punto de degradación: escalón 7, 20 usuarios (p95 de 1254 ms). Capacidad dentro del objetivo: 15.0 peticiones por segundo con 15 usuarios (p95 de 241 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 100 | 2.0 | 2.8 | 42 | 69 | 91 | 93 | 0.00 % | 6 % y 24 % | 218 |
| 2 | 4 | 200 | 4.0 | 6.1 | 22 | 62 | 88 | 202 | 0.00 % | 8 % y 11 % | 218 |
| 3 | 6 | 300 | 6.0 | 9.5 | 33 | 50 | 56 | 60 | 0.00 % | 11 % y 16 % | 219 |
| 4 | 8 | 400 | 8.0 | 12.2 | 44 | 99 | 163 | 261 | 0.00 % | 21 % y 48 % | 219 |
| 5 | 10 | 500 | 10.0 | 15.1 | 51 | 165 | 865 | 1028 | 0.00 % | 31 % y 97 % | 222 |
| 6 | 15 | 750 | 15.0 | 23.2 | 65 | 241 | 324 | 387 | 0.00 % | 46 % y 74 % | 235 |
| 7 | 20 | 976 | 19.5 | 28.6 | 302 | 1254 (sobre el objetivo) | 1431 | 1607 | 0.00 % | 89 % y 105 % | 240 |
| 8 | 30 | 1,118 | 22.4 | 33.9 | 1274 | 1933 (sobre el objetivo) | 2357 | 2441 | 0.00 % | 101 % y 102 % | 243 |
| 9 | 60 | 1,104 | 22.1 | 32.9 | 2605 | 3547 (sobre el objetivo) | 4010 | 4628 | 0.00 % | 101 % y 102 % | 247 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 10 | 16 | 1.3 | 43 | 76 | 0.5 | 43 | 69 |
| 2 | 4 | 0.4 | 4 | 15 | 2.4 | 26 | 61 | 1.2 | 30 | 74 |
| 3 | 6 | 0.7 | 8 | 15 | 3.3 | 34 | 50 | 2.1 | 35 | 51 |
| 4 | 8 | 0.9 | 13 | 24 | 4.6 | 47 | 110 | 2.5 | 47 | 96 |
| 5 | 10 | 1.0 | 9 | 28 | 5.9 | 54 | 167 | 3.1 | 56 | 190 |
| 6 | 15 | 1.5 | 12 | 42 | 8.6 | 72 | 240 | 4.9 | 73 | 276 |
| 7 | 20 | 2.0 | 58 | 314 | 12.0 | 359 | 1242 | 5.5 | 355 | 1350 |
| 8 | 30 | 2.5 | 128 | 544 | 12.9 | 1326 | 1934 | 7.0 | 1338 | 1970 |
| 9 | 60 | 2.7 | 1570 | 2421 | 12.6 | 2639 | 3589 | 6.8 | 2774 | 3647 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 5.8 % | 24.0 % | 218 | 0.4 % | 3.0 % | 408 | 0.3 % | 0.4 % | 42 |
| 2 | 4 | 7.5 % | 10.9 % | 218 | 2.4 % | 32.4 % | 404 | 0.5 % | 0.6 % | 42 |
| 3 | 6 | 11.2 % | 16.0 % | 219 | 1.8 % | 24.5 % | 404 | 0.8 % | 0.9 % | 42 |
| 4 | 8 | 21.1 % | 47.8 % | 219 | 2.7 % | 25.1 % | 414 | 1.0 % | 1.2 % | 43 |
| 5 | 10 | 31.1 % | 97.4 % | 222 | 2.5 % | 36.0 % | 404 | 1.3 % | 2.0 % | 43 |
| 6 | 15 | 46.0 % | 74.0 % | 235 | 1.2 % | 15.4 % | 404 | 1.7 % | 2.2 % | 44 |
| 7 | 20 | 88.6 % | 105.1 % | 240 | 2.0 % | 26.7 % | 416 | 2.9 % | 3.3 % | 44 |
| 8 | 30 | 100.7 % | 101.8 % | 243 | 2.8 % | 38.4 % | 404 | 2.7 % | 3.8 % | 45 |
| 9 | 60 | 100.7 % | 102.0 % | 247 | 2.8 % | 40.0 % | 404 | 2.8 % | 5.6 % | 47 |

## Corrida `un_proceso_en_serie`

1 proceso, 1 CPU, 1 petición a la vez por proceso y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 18.42 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 14:56:25.

Punto de degradación: escalón 8, 30 usuarios (p95 de 1420 ms). Capacidad dentro del objetivo: 20.0 peticiones por segundo con 20 usuarios (p95 de 108 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 35 | 81 | 141 | 142 | 0.00 % | 8 % y 50 % | 227 |
| 2 | 4 | 200 | 4.0 | 6.1 | 23 | 45 | 55 | 286 | 0.00 % | 8 % y 24 % | 228 |
| 3 | 6 | 300 | 6.0 | 9.5 | 26 | 46 | 86 | 100 | 0.00 % | 11 % y 37 % | 218 |
| 4 | 8 | 400 | 8.0 | 12.2 | 28 | 62 | 108 | 140 | 0.00 % | 15 % y 34 % | 219 |
| 5 | 10 | 500 | 10.0 | 15.1 | 36 | 89 | 143 | 306 | 0.00 % | 17 % y 25 % | 218 |
| 6 | 15 | 750 | 15.0 | 23.2 | 41 | 133 | 346 | 455 | 0.00 % | 26 % y 45 % | 218 |
| 7 | 20 | 1,000 | 20.0 | 29.2 | 52 | 108 | 173 | 212 | 0.00 % | 37 % y 56 % | 218 |
| 8 | 30 | 1,438 | 28.8 | 44.0 | 143 | 1420 (sobre el objetivo) | 2399 | 2652 | 0.00 % | 68 % y 102 % | 231 |
| 9 | 60 | 2,197 | 43.9 | 65.6 | 1235 | 2327 (sobre el objetivo) | 2879 | 2942 | 0.00 % | 100 % y 101 % | 231 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 24 | 45 | 1.3 | 38 | 78 | 0.5 | 34 | 141 |
| 2 | 4 | 0.4 | 6 | 286 | 2.4 | 24 | 45 | 1.2 | 24 | 43 |
| 3 | 6 | 0.7 | 16 | 23 | 3.3 | 27 | 46 | 2.1 | 28 | 50 |
| 4 | 8 | 0.9 | 17 | 28 | 4.6 | 29 | 61 | 2.5 | 31 | 70 |
| 5 | 10 | 1.0 | 20 | 65 | 5.9 | 36 | 89 | 3.1 | 37 | 102 |
| 6 | 15 | 1.5 | 23 | 92 | 8.6 | 42 | 133 | 4.9 | 43 | 154 |
| 7 | 20 | 2.0 | 36 | 85 | 12.3 | 55 | 111 | 5.6 | 52 | 119 |
| 8 | 30 | 2.9 | 141 | 1361 | 16.8 | 142 | 1394 | 9.1 | 156 | 1472 |
| 9 | 60 | 4.6 | 1082 | 2329 | 26.2 | 1254 | 2321 | 13.1 | 1246 | 2332 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 8.0 % | 49.7 % | 227 | 2.1 % | 27.6 % | 432 | 0.3 % | 0.6 % | 42 |
| 2 | 4 | 8.2 % | 24.3 % | 228 | 3.9 % | 30.1 % | 432 | 0.5 % | 0.8 % | 42 |
| 3 | 6 | 10.6 % | 36.8 % | 218 | 0.2 % | 0.3 % | 432 | 0.7 % | 0.9 % | 42 |
| 4 | 8 | 14.7 % | 34.4 % | 219 | 0.2 % | 0.3 % | 432 | 0.9 % | 1.2 % | 43 |
| 5 | 10 | 17.0 % | 25.0 % | 218 | 3.7 % | 30.5 % | 446 | 1.1 % | 1.4 % | 43 |
| 6 | 15 | 25.9 % | 45.1 % | 218 | 2.4 % | 32.8 % | 432 | 1.4 % | 1.9 % | 43 |
| 7 | 20 | 36.5 % | 55.6 % | 218 | 2.0 % | 27.8 % | 433 | 1.7 % | 2.1 % | 44 |
| 8 | 30 | 67.9 % | 102.3 % | 231 | 2.1 % | 28.7 % | 433 | 2.6 % | 3.6 % | 45 |
| 9 | 60 | 99.8 % | 100.6 % | 231 | 5.8 % | 48.6 % | 443 | 3.2 % | 3.9 % | 47 |

Variación frente a sus repeticiones:

| Escalón | Usuarios | Peticiones/s, `un_proceso_en_serie` | Peticiones/s, `un_proceso_en_serie_r2` | Peticiones/s, `un_proceso_en_serie_r3` | Peticiones/s, `un_proceso_en_serie_r4` | p95 (ms), `un_proceso_en_serie` | p95 (ms), `un_proceso_en_serie_r2` | p95 (ms), `un_proceso_en_serie_r3` | p95 (ms), `un_proceso_en_serie_r4` | p95 mayor entre p95 menor |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 2.0 | 2.0 | 2.0 | 2.0 | 81 | 49 | 60 | 84 | 1.7 |
| 2 | 4 | 4.0 | 4.0 | 4.0 | 4.0 | 45 | 104 | 35 | 54 | 3.0 |
| 3 | 6 | 6.0 | 6.0 | 6.0 | 6.0 | 46 | 48 | 33 | 70 | 2.1 |
| 4 | 8 | 8.0 | 8.0 | 8.0 | 8.0 | 62 | 54 | 272 | 79 | 5.1 |
| 5 | 10 | 10.0 | 10.0 | 10.0 | 10.0 | 89 | 51 | 72 | 58 | 1.8 |
| 6 | 15 | 15.0 | 15.0 | 15.0 | 15.0 | 133 | 59 | 96 | 98 | 2.3 |
| 7 | 20 | 20.0 | 20.0 | 20.0 | 20.0 | 108 | 101 | 80 | 172 | 2.1 |
| 8 | 30 | 28.8 | 30.0 | 30.0 | 30.0 | 1420 | 228 | 313 | 202 | 7.0 |
| 9 | 60 | 43.9 | 54.2 | 45.9 | 52.1 | 2327 | 1469 | 1917 | 1579 | 1.6 |

## Corrida `un_proceso_en_serie_r2`

1 proceso, 1 CPU, 1 petición a la vez por proceso y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 11.81 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 15:25:11.

Punto de degradación: escalón 9, 60 usuarios (p95 de 1469 ms). Capacidad dentro del objetivo: 30.0 peticiones por segundo con 30 usuarios (p95 de 228 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 30 | 49 | 59 | 60 | 0.00 % | 7 % y 36 % | 218 |
| 2 | 4 | 200 | 4.0 | 6.1 | 37 | 104 | 274 | 361 | 0.00 % | 18 % y 67 % | 218 |
| 3 | 6 | 300 | 6.0 | 9.5 | 29 | 48 | 63 | 85 | 0.00 % | 13 % y 44 % | 218 |
| 4 | 8 | 400 | 8.0 | 12.2 | 28 | 54 | 112 | 174 | 0.00 % | 20 % y 50 % | 226 |
| 5 | 10 | 500 | 10.0 | 15.1 | 28 | 51 | 88 | 106 | 0.00 % | 15 % y 24 % | 218 |
| 6 | 15 | 750 | 15.0 | 23.2 | 28 | 59 | 72 | 130 | 0.00 % | 20 % y 28 % | 228 |
| 7 | 20 | 1,000 | 20.0 | 29.2 | 47 | 101 | 145 | 176 | 0.00 % | 33 % y 70 % | 222 |
| 8 | 30 | 1,500 | 30.0 | 46.0 | 67 | 228 | 439 | 539 | 0.00 % | 42 % y 75 % | 218 |
| 9 | 60 | 2,712 | 54.2 | 82.1 | 928 | 1469 (sobre el objetivo) | 1783 | 1868 | 0.00 % | 98 % y 101 % | 219 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 16 | 34 | 1.3 | 30 | 48 | 0.5 | 31 | 59 |
| 2 | 4 | 0.4 | 6 | 188 | 2.4 | 38 | 99 | 1.2 | 37 | 150 |
| 3 | 6 | 0.7 | 18 | 29 | 3.3 | 30 | 53 | 2.1 | 32 | 48 |
| 4 | 8 | 0.9 | 17 | 31 | 4.6 | 29 | 55 | 2.5 | 31 | 53 |
| 5 | 10 | 1.0 | 17 | 30 | 5.9 | 29 | 59 | 3.1 | 30 | 50 |
| 6 | 15 | 1.5 | 16 | 41 | 8.6 | 29 | 59 | 4.9 | 30 | 62 |
| 7 | 20 | 2.0 | 25 | 71 | 12.3 | 47 | 109 | 5.6 | 48 | 101 |
| 8 | 30 | 3.1 | 49 | 155 | 17.4 | 69 | 196 | 9.5 | 69 | 244 |
| 9 | 60 | 5.5 | 927 | 1441 | 32.0 | 929 | 1473 | 16.7 | 926 | 1468 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 7.4 % | 35.8 % | 218 | 0.2 % | 0.3 % | 433 | 0.3 % | 0.4 % | 42 |
| 2 | 4 | 17.8 % | 67.0 % | 218 | 4.0 % | 56.7 % | 433 | 0.7 % | 1.0 % | 42 |
| 3 | 6 | 12.8 % | 43.8 % | 218 | 0.2 % | 0.3 % | 433 | 0.8 % | 0.9 % | 42 |
| 4 | 8 | 19.5 % | 50.5 % | 226 | 0.2 % | 0.3 % | 433 | 1.0 % | 1.8 % | 43 |
| 5 | 10 | 15.5 % | 24.3 % | 218 | 1.5 % | 19.2 % | 433 | 1.1 % | 1.4 % | 43 |
| 6 | 15 | 20.0 % | 27.5 % | 228 | 1.9 % | 25.8 % | 433 | 1.5 % | 1.6 % | 43 |
| 7 | 20 | 33.1 % | 70.1 % | 222 | 2.0 % | 27.9 % | 444 | 1.8 % | 2.3 % | 44 |
| 8 | 30 | 41.7 % | 75.3 % | 218 | 0.2 % | 0.2 % | 433 | 2.2 % | 2.7 % | 44 |
| 9 | 60 | 98.3 % | 100.6 % | 219 | 3.0 % | 37.9 % | 433 | 3.9 % | 4.4 % | 47 |

## Corrida `un_proceso_en_serie_r3`

1 proceso, 1 CPU, 1 petición a la vez por proceso y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 22.92 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 17:09:07.

Punto de degradación: escalón 9, 60 usuarios (p95 de 1917 ms; 45.9 peticiones por segundo de 60 ofrecidas). Capacidad dentro del objetivo: 30.0 peticiones por segundo con 30 usuarios (p95 de 313 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 34 | 60 | 68 | 68 | 0.00 % | 6 % y 34 % | 218 |
| 2 | 4 | 200 | 4.0 | 6.1 | 20 | 35 | 52 | 140 | 0.00 % | 10 % y 37 % | 231 |
| 3 | 6 | 300 | 6.0 | 9.5 | 24 | 33 | 51 | 74 | 0.00 % | 9 % y 29 % | 219 |
| 4 | 8 | 400 | 8.0 | 12.2 | 31 | 272 | 441 | 657 | 0.00 % | 18 % y 47 % | 218 |
| 5 | 10 | 500 | 10.0 | 15.1 | 32 | 72 | 143 | 158 | 0.00 % | 20 % y 42 % | 218 |
| 6 | 15 | 750 | 15.0 | 23.2 | 36 | 96 | 183 | 228 | 0.00 % | 25 % y 56 % | 219 |
| 7 | 20 | 1,002 | 20.0 | 29.3 | 39 | 80 | 96 | 158 | 0.00 % | 27 % y 50 % | 219 |
| 8 | 30 | 1,500 | 30.0 | 46.0 | 117 | 313 | 586 | 808 | 0.00 % | 58 % y 98 % | 229 |
| 9 | 60 | 2,293 | 45.9 | 69.2 | 1240 | 1917 (sobre el objetivo) | 2133 | 2146 | 0.00 % | 100 % y 101 % | 232 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 19 | 35 | 1.3 | 35 | 62 | 0.5 | 34 | 55 |
| 2 | 4 | 0.4 | 5 | 23 | 2.4 | 22 | 37 | 1.2 | 21 | 34 |
| 3 | 6 | 0.7 | 15 | 23 | 3.3 | 24 | 36 | 2.1 | 25 | 32 |
| 4 | 8 | 0.9 | 19 | 118 | 4.6 | 32 | 293 | 2.5 | 31 | 259 |
| 5 | 10 | 1.0 | 18 | 36 | 5.9 | 34 | 71 | 3.1 | 34 | 79 |
| 6 | 15 | 1.5 | 28 | 93 | 8.6 | 37 | 104 | 4.9 | 36 | 95 |
| 7 | 20 | 2.0 | 28 | 62 | 12.4 | 41 | 81 | 5.6 | 46 | 82 |
| 8 | 30 | 3.1 | 101 | 308 | 17.4 | 119 | 313 | 9.5 | 114 | 315 |
| 9 | 60 | 4.6 | 1204 | 1867 | 27.2 | 1240 | 1939 | 14.0 | 1248 | 1893 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 5.5 % | 34.0 % | 218 | 2.0 % | 17.4 % | 412 | 0.3 % | 0.6 % | 42 |
| 2 | 4 | 9.9 % | 36.5 % | 231 | 3.6 % | 27.6 % | 402 | 0.6 % | 0.7 % | 42 |
| 3 | 6 | 9.1 % | 29.3 % | 219 | 0.7 % | 7.8 % | 402 | 0.7 % | 0.8 % | 42 |
| 4 | 8 | 18.0 % | 46.6 % | 218 | 0.3 % | 0.4 % | 402 | 1.2 % | 2.6 % | 43 |
| 5 | 10 | 20.2 % | 41.5 % | 218 | 0.5 % | 3.5 % | 402 | 1.2 % | 1.4 % | 43 |
| 6 | 15 | 25.4 % | 56.4 % | 219 | 3.4 % | 50.7 % | 402 | 1.4 % | 2.5 % | 43 |
| 7 | 20 | 27.5 % | 50.2 % | 219 | 0.7 % | 7.2 % | 402 | 1.7 % | 1.9 % | 44 |
| 8 | 30 | 58.5 % | 98.1 % | 229 | 3.6 % | 38.0 % | 412 | 2.4 % | 3.4 % | 45 |
| 9 | 60 | 100.1 % | 101.1 % | 232 | 6.3 % | 51.4 % | 402 | 3.5 % | 4.7 % | 47 |

## Corrida `un_proceso_en_serie_r4`

1 proceso, 1 CPU, 1 petición a la vez por proceso y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 10.25 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 17:51:05.

Punto de degradación: escalón 9, 60 usuarios (p95 de 1579 ms; 52.1 peticiones por segundo de 60 ofrecidas). Capacidad dentro del objetivo: 30.0 peticiones por segundo con 30 usuarios (p95 de 202 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 35 | 84 | 91 | 92 | 0.00 % | 6 % y 34 % | 218 |
| 2 | 4 | 200 | 4.0 | 6.1 | 23 | 54 | 70 | 255 | 0.00 % | 10 % y 36 % | 218 |
| 3 | 6 | 298 | 6.0 | 9.4 | 30 | 70 | 87 | 100 | 0.00 % | 14 % y 48 % | 218 |
| 4 | 8 | 400 | 8.0 | 12.2 | 32 | 79 | 143 | 252 | 0.00 % | 18 % y 58 % | 226 |
| 5 | 10 | 500 | 10.0 | 15.1 | 32 | 58 | 91 | 109 | 0.00 % | 20 % y 55 % | 218 |
| 6 | 15 | 750 | 15.0 | 23.2 | 40 | 98 | 178 | 186 | 0.00 % | 28 % y 54 % | 218 |
| 7 | 20 | 1,000 | 20.0 | 29.2 | 57 | 172 | 331 | 450 | 0.00 % | 40 % y 50 % | 217 |
| 8 | 30 | 1,500 | 30.0 | 46.0 | 85 | 202 | 227 | 249 | 0.00 % | 49 % y 76 % | 218 |
| 9 | 60 | 2,605 | 52.1 | 79.2 | 1017 | 1579 (sobre el objetivo) | 1655 | 1684 | 0.00 % | 100 % y 101 % | 231 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 21 | 30 | 1.3 | 35 | 85 | 0.5 | 34 | 65 |
| 2 | 4 | 0.4 | 8 | 51 | 2.4 | 25 | 66 | 1.2 | 21 | 54 |
| 3 | 6 | 0.7 | 20 | 43 | 3.2 | 31 | 70 | 2.1 | 31 | 74 |
| 4 | 8 | 0.9 | 18 | 34 | 4.6 | 33 | 79 | 2.5 | 34 | 91 |
| 5 | 10 | 1.0 | 19 | 32 | 5.9 | 32 | 58 | 3.1 | 32 | 59 |
| 6 | 15 | 1.5 | 22 | 74 | 8.6 | 41 | 100 | 4.9 | 43 | 99 |
| 7 | 20 | 2.0 | 37 | 123 | 12.3 | 63 | 172 | 5.6 | 62 | 209 |
| 8 | 30 | 3.1 | 64 | 174 | 17.4 | 90 | 207 | 9.5 | 82 | 200 |
| 9 | 60 | 5.2 | 981 | 1580 | 30.7 | 1017 | 1569 | 16.2 | 1046 | 1583 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 6.0 % | 34.5 % | 218 | 2.3 % | 30.7 % | 404 | 0.3 % | 0.4 % | 42 |
| 2 | 4 | 10.5 % | 35.9 % | 218 | 4.0 % | 30.5 % | 404 | 0.6 % | 0.7 % | 42 |
| 3 | 6 | 14.2 % | 48.1 % | 218 | 0.2 % | 0.3 % | 404 | 0.8 % | 1.0 % | 42 |
| 4 | 8 | 18.2 % | 57.9 % | 226 | 3.5 % | 31.2 % | 413 | 0.9 % | 1.4 % | 43 |
| 5 | 10 | 20.0 % | 54.7 % | 218 | 2.2 % | 30.1 % | 404 | 1.1 % | 1.4 % | 43 |
| 6 | 15 | 28.0 % | 54.1 % | 218 | 2.5 % | 35.0 % | 404 | 1.4 % | 1.7 % | 43 |
| 7 | 20 | 39.7 % | 50.0 % | 217 | 4.6 % | 41.0 % | 404 | 1.8 % | 2.3 % | 44 |
| 8 | 30 | 49.3 % | 76.2 % | 218 | 2.2 % | 24.2 % | 409 | 2.1 % | 2.6 % | 44 |
| 9 | 60 | 100.1 % | 101.2 % | 231 | 3.8 % | 36.5 % | 414 | 3.7 % | 5.0 % | 47 |

## Corrida `dos_procesos_un_cpu`

2 procesos, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 31.41 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 14:17:11.

Punto de degradación: escalón 6, 15 usuarios (p95 de 1567 ms). Capacidad dentro del objetivo: 10.0 peticiones por segundo con 10 usuarios (p95 de 72 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 39 | 74 | 93 | 96 | 0.00 % | 8 % y 39 % | 457 |
| 2 | 4 | 200 | 4.0 | 6.1 | 32 | 94 | 161 | 257 | 0.00 % | 11 % y 34 % | 450 |
| 3 | 6 | 300 | 6.0 | 9.5 | 44 | 211 | 329 | 503 | 0.00 % | 23 % y 50 % | 461 |
| 4 | 8 | 400 | 8.0 | 12.2 | 21 | 84 | 158 | 205 | 0.00 % | 21 % y 45 % | 464 |
| 5 | 10 | 500 | 10.0 | 15.1 | 20 | 72 | 102 | 129 | 0.00 % | 20 % y 43 % | 451 |
| 6 | 15 | 707 | 14.1 | 22.1 | 120 | 1567 (sobre el objetivo) | 2215 | 2775 | 0.00 % | 79 % y 101 % | 465 |
| 7 | 20 | 869 | 17.4 | 25.8 | 332 | 1897 (sobre el objetivo) | 2811 | 3288 | 0.00 % | 92 % y 106 % | 469 |
| 8 | 30 | 774 | 15.5 | 23.4 | 1867 | 3012 (sobre el objetivo) | 3692 | 4472 | 0.00 % | 101 % y 104 % | 473 |
| 9 | 60 | 572 | 11.4 | 0.0 | 5004 | 5033 (sobre el objetivo) | 6327 | 6530 | 98.95 % | 100 % y 105 % | 476 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 12 | 15 | 1.3 | 39 | 74 | 0.5 | 40 | 78 |
| 2 | 4 | 0.4 | 5 | 56 | 2.4 | 35 | 94 | 1.2 | 34 | 84 |
| 3 | 6 | 0.7 | 4 | 31 | 3.3 | 50 | 167 | 2.1 | 48 | 236 |
| 4 | 8 | 0.9 | 3 | 17 | 4.6 | 23 | 108 | 2.5 | 23 | 82 |
| 5 | 10 | 1.0 | 4 | 16 | 5.9 | 23 | 80 | 3.1 | 22 | 67 |
| 6 | 15 | 1.4 | 49 | 227 | 8.1 | 123 | 1567 | 4.7 | 182 | 1679 |
| 7 | 20 | 1.8 | 92 | 324 | 10.5 | 373 | 1891 | 5.1 | 502 | 2004 |
| 8 | 30 | 1.6 | 304 | 544 | 9.1 | 1912 | 2916 | 4.8 | 2012 | 3192 |
| 9 | 60 | 1.4 | 5004 | 5019 | 6.4 | 5004 | 5037 | 3.7 | 5004 | 5044 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 7.6 % | 39.1 % | 457 | 1.7 % | 22.4 % | 431 | 0.6 % | 3.9 % | 42 |
| 2 | 4 | 11.1 % | 33.8 % | 450 | 5.3 % | 51.6 % | 432 | 0.6 % | 0.8 % | 43 |
| 3 | 6 | 23.2 % | 50.4 % | 461 | 5.5 % | 79.7 % | 431 | 0.9 % | 1.5 % | 43 |
| 4 | 8 | 21.4 % | 45.3 % | 464 | 1.9 % | 25.6 % | 431 | 1.0 % | 1.4 % | 43 |
| 5 | 10 | 20.3 % | 42.7 % | 451 | 2.5 % | 30.0 % | 435 | 1.1 % | 1.3 % | 43 |
| 6 | 15 | 78.8 % | 101.4 % | 465 | 3.2 % | 45.2 % | 431 | 2.5 % | 3.1 % | 44 |
| 7 | 20 | 91.8 % | 106.1 % | 469 | 3.1 % | 42.8 % | 431 | 2.9 % | 3.6 % | 44 |
| 8 | 30 | 100.8 % | 103.8 % | 473 | 2.0 % | 26.7 % | 442 | 2.2 % | 3.6 % | 45 |
| 9 | 60 | 100.5 % | 104.9 % | 476 | 19.1 % | 100.6 % | 443 | 4.5 % | 7.0 % | 52 |

Variación frente a sus repeticiones:

| Escalón | Usuarios | Peticiones/s, `dos_procesos_un_cpu` | Peticiones/s, `dos_procesos_un_cpu_r2` | p95 (ms), `dos_procesos_un_cpu` | p95 (ms), `dos_procesos_un_cpu_r2` | p95 mayor entre p95 menor |
|---|---|---|---|---|---|---|
| 1 | 2 | 2.0 | 2.0 | 74 | 107 | 1.4 |
| 2 | 4 | 4.0 | 4.0 | 94 | 59 | 1.6 |
| 3 | 6 | 6.0 | 6.0 | 211 | 76 | 2.8 |
| 4 | 8 | 8.0 | 8.0 | 84 | 115 | 1.4 |
| 5 | 10 | 10.0 | 9.7 | 72 | 135 | 1.9 |
| 6 | 15 | 14.1 | 15.1 | 1567 | 450 | 3.5 |
| 7 | 20 | 17.4 | 18.6 | 1897 | 1565 | 1.2 |
| 8 | 30 | 15.5 | 19.0 | 3012 | 2401 | 1.3 |
| 9 | 60 | 11.4 | 18.8 | 5033 | 5001 | 1.0 |

## Corrida `dos_procesos_un_cpu_r2`

2 procesos, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 21.83 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 18:09:58.

Punto de degradación: escalón 7, 20 usuarios (p95 de 1565 ms). Capacidad dentro del objetivo: 15.1 peticiones por segundo con 15 usuarios (p95 de 450 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 45 | 107 | 140 | 142 | 0.00 % | 8 % y 30 % | 462 |
| 2 | 4 | 200 | 4.0 | 6.1 | 19 | 59 | 114 | 173 | 0.00 % | 11 % y 33 % | 453 |
| 3 | 6 | 300 | 6.0 | 9.5 | 36 | 76 | 112 | 135 | 0.00 % | 14 % y 20 % | 453 |
| 4 | 8 | 401 | 8.0 | 12.2 | 20 | 115 | 348 | 474 | 0.00 % | 23 % y 100 % | 466 |
| 5 | 10 | 485 | 9.7 | 14.6 | 20 | 135 | 381 | 4667 | 0.21 % | 33 % y 100 % | 454 |
| 6 | 15 | 753 | 15.1 | 23.4 | 36 | 450 | 735 | 923 | 0.00 % | 48 % y 87 % | 465 |
| 7 | 20 | 932 | 18.6 | 27.3 | 54 | 1565 (sobre el objetivo) | 1951 | 2291 | 0.00 % | 66 % y 103 % | 472 |
| 8 | 30 | 952 | 19.0 | 29.0 | 1524 | 2401 (sobre el objetivo) | 3123 | 3508 | 0.00 % | 101 % y 104 % | 476 |
| 9 | 60 | 939 | 18.8 | 25.9 | 3160 | 5001 (sobre el objetivo) | 5003 | 5061 | 6.50 % | 102 % y 105 % | 487 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 11 | 19 | 1.3 | 47 | 110 | 0.5 | 45 | 105 |
| 2 | 4 | 0.4 | 3 | 18 | 2.4 | 22 | 57 | 1.2 | 19 | 69 |
| 3 | 6 | 0.7 | 9 | 14 | 3.3 | 38 | 75 | 2.1 | 40 | 79 |
| 4 | 8 | 0.9 | 3 | 47 | 4.6 | 20 | 144 | 2.5 | 20 | 94 |
| 5 | 10 | 1.0 | 3 | 9 | 5.7 | 21 | 114 | 3.0 | 21 | 174 |
| 6 | 15 | 1.5 | 3 | 136 | 8.7 | 41 | 495 | 4.9 | 61 | 405 |
| 7 | 20 | 1.8 | 8 | 231 | 11.6 | 55 | 1533 | 5.2 | 66 | 1688 |
| 8 | 30 | 2.1 | 244 | 392 | 10.9 | 1542 | 2304 | 6.0 | 1676 | 2600 |
| 9 | 60 | 2.1 | 547 | 2674 | 11.0 | 3212 | 5001 | 5.7 | 3323 | 5001 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 8.2 % | 29.8 % | 462 | 4.4 % | 36.5 % | 405 | 0.3 % | 0.4 % | 42 |
| 2 | 4 | 10.9 % | 32.7 % | 453 | 2.2 % | 30.1 % | 405 | 0.5 % | 0.8 % | 42 |
| 3 | 6 | 13.5 % | 19.7 % | 453 | 3.6 % | 28.4 % | 405 | 0.7 % | 1.0 % | 42 |
| 4 | 8 | 23.2 % | 99.8 % | 466 | 2.2 % | 29.8 % | 405 | 1.3 % | 2.3 % | 43 |
| 5 | 10 | 33.1 % | 99.7 % | 454 | 2.5 % | 26.3 % | 405 | 1.5 % | 2.3 % | 43 |
| 6 | 15 | 47.6 % | 86.6 % | 465 | 2.8 % | 39.4 % | 405 | 1.9 % | 2.4 % | 43 |
| 7 | 20 | 65.8 % | 103.4 % | 472 | 2.7 % | 35.6 % | 405 | 2.5 % | 3.5 % | 44 |
| 8 | 30 | 100.5 % | 104.0 % | 476 | 1.1 % | 11.0 % | 405 | 2.5 % | 3.0 % | 45 |
| 9 | 60 | 101.5 % | 105.2 % | 487 | 2.9 % | 28.3 % | 418 | 2.7 % | 8.7 % | 47 |

## Corrida `dos_procesos`

2 procesos, 2 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 31.1 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 14:07:16.

Punto de degradación: escalón 7, 20 usuarios (p95 de 1364 ms). Capacidad dentro del objetivo: 15.0 peticiones por segundo con 15 usuarios (p95 de 148 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 100 | 2.0 | 2.8 | 59 | 128 | 184 | 186 | 0.00 % | 13 % y 45 % | 458 |
| 2 | 4 | 200 | 4.0 | 6.1 | 29 | 109 | 160 | 340 | 0.00 % | 13 % y 42 % | 451 |
| 3 | 6 | 300 | 6.0 | 9.5 | 28 | 93 | 151 | 200 | 0.00 % | 18 % y 27 % | 452 |
| 4 | 8 | 388 | 7.8 | 11.8 | 38 | 145 | 4063 | 4630 | 0.26 % | 37 % y 186 % | 465 |
| 5 | 10 | 500 | 10.0 | 15.0 | 52 | 172 | 256 | 317 | 0.00 % | 38 % y 54 % | 463 |
| 6 | 15 | 750 | 15.0 | 23.3 | 34 | 148 | 282 | 373 | 0.00 % | 50 % y 80 % | 467 |
| 7 | 20 | 958 | 19.2 | 28.1 | 177 | 1364 (sobre el objetivo) | 1896 | 2492 | 0.00 % | 135 % y 214 % | 466 |
| 8 | 30 | 950 | 19.0 | 29.0 | 1588 | 2227 (sobre el objetivo) | 2355 | 2460 | 0.00 % | 205 % y 208 % | 470 |
| 9 | 60 | 1,154 | 23.1 | 34.5 | 1876 | 4376 (sobre el objetivo) | 4620 | 4787 | 0.00 % | 206 % y 210 % | 486 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 14 | 24 | 1.3 | 65 | 119 | 0.5 | 62 | 131 |
| 2 | 4 | 0.4 | 5 | 25 | 2.4 | 33 | 131 | 1.2 | 32 | 105 |
| 3 | 6 | 0.7 | 4 | 24 | 3.3 | 30 | 92 | 2.1 | 28 | 102 |
| 4 | 8 | 0.9 | 5 | 23 | 4.4 | 44 | 145 | 2.5 | 50 | 165 |
| 5 | 10 | 1.1 | 8 | 33 | 5.9 | 62 | 192 | 3.0 | 54 | 196 |
| 6 | 15 | 1.5 | 4 | 28 | 8.6 | 46 | 169 | 4.9 | 36 | 132 |
| 7 | 20 | 1.9 | 28 | 144 | 11.9 | 198 | 1443 | 5.4 | 209 | 1468 |
| 8 | 30 | 2.0 | 72 | 220 | 11.0 | 1667 | 2228 | 6.0 | 1676 | 2253 |
| 9 | 60 | 2.5 | 71 | 331 | 13.7 | 1958 | 4376 | 6.9 | 2452 | 4428 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 12.8 % | 44.6 % | 458 | 0.3 % | 0.3 % | 430 | 0.4 % | 0.6 % | 42 |
| 2 | 4 | 12.5 % | 42.1 % | 451 | 1.8 % | 23.0 % | 431 | 0.7 % | 0.8 % | 42 |
| 3 | 6 | 17.9 % | 27.5 % | 452 | 4.4 % | 31.8 % | 431 | 0.9 % | 1.2 % | 43 |
| 4 | 8 | 37.4 % | 186.4 % | 465 | 1.3 % | 15.5 % | 430 | 1.2 % | 1.6 % | 43 |
| 5 | 10 | 37.5 % | 54.4 % | 463 | 4.9 % | 35.6 % | 443 | 1.6 % | 2.5 % | 43 |
| 6 | 15 | 50.1 % | 79.6 % | 467 | 0.2 % | 0.3 % | 430 | 2.1 % | 3.0 % | 43 |
| 7 | 20 | 135.4 % | 214.1 % | 466 | 1.8 % | 23.1 % | 430 | 3.6 % | 6.1 % | 44 |
| 8 | 30 | 205.3 % | 208.5 % | 470 | 3.3 % | 28.2 % | 430 | 4.2 % | 5.7 % | 45 |
| 9 | 60 | 205.6 % | 210.3 % | 486 | 8.2 % | 66.5 % | 430 | 4.2 % | 6.1 % | 47 |

Variación frente a sus repeticiones:

| Escalón | Usuarios | Peticiones/s, `dos_procesos` | Peticiones/s, `dos_procesos_r2` | Peticiones/s, `dos_procesos_r3` | p95 (ms), `dos_procesos` | p95 (ms), `dos_procesos_r2` | p95 (ms), `dos_procesos_r3` | p95 mayor entre p95 menor |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 2.0 | 2.0 | 2.0 | 128 | 129 | 70 | 1.8 |
| 2 | 4 | 4.0 | 4.0 | 4.0 | 109 | 111 | 57 | 1.9 |
| 3 | 6 | 6.0 | 6.0 | 6.0 | 93 | 72 | 53 | 1.8 |
| 4 | 8 | 7.8 | 7.9 | 8.0 | 145 | 100 | 89 | 1.6 |
| 5 | 10 | 10.0 | 10.0 | 10.0 | 172 | 182 | 60 | 3.0 |
| 6 | 15 | 15.0 | 14.8 | 15.0 | 148 | 918 | 113 | 8.1 |
| 7 | 20 | 19.2 | 19.3 | 20.0 | 1364 | 1284 | 146 | 9.3 |
| 8 | 30 | 19.0 | 26.4 | 30.0 | 2227 | 1706 | 266 | 8.4 |
| 9 | 60 | 23.1 | 25.5 | 28.4 | 4376 | 3328 | 3032 | 1.4 |

## Corrida `dos_procesos_r2`

2 procesos, 2 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 31.72 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 14:41:14.

Punto de degradación: escalón 6, 15 usuarios (p95 de 918 ms). Capacidad dentro del objetivo: 10.0 peticiones por segundo con 10 usuarios (p95 de 182 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 51 | 129 | 152 | 155 | 0.00 % | 11 % y 44 % | 461 |
| 2 | 4 | 200 | 4.0 | 6.1 | 32 | 111 | 151 | 201 | 0.00 % | 15 % y 49 % | 451 |
| 3 | 6 | 300 | 6.0 | 9.5 | 23 | 72 | 111 | 160 | 0.00 % | 18 % y 53 % | 451 |
| 4 | 8 | 397 | 7.9 | 12.1 | 27 | 100 | 358 | 2388 | 0.00 % | 26 % y 134 % | 455 |
| 5 | 10 | 500 | 10.0 | 15.1 | 39 | 182 | 232 | 380 | 0.00 % | 34 % y 61 % | 452 |
| 6 | 15 | 742 | 14.8 | 23.0 | 87 | 918 (sobre el objetivo) | 1407 | 1590 | 0.00 % | 83 % y 180 % | 456 |
| 7 | 20 | 965 | 19.3 | 28.4 | 152 | 1284 (sobre el objetivo) | 1846 | 2193 | 0.00 % | 131 % y 203 % | 470 |
| 8 | 30 | 1,319 | 26.4 | 40.3 | 649 | 1706 (sobre el objetivo) | 2249 | 2845 | 0.00 % | 182 % y 207 % | 463 |
| 9 | 60 | 1,275 | 25.5 | 37.5 | 2392 | 3328 (sobre el objetivo) | 3669 | 3912 | 0.00 % | 203 % y 209 % | 486 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 15 | 20 | 1.3 | 53 | 129 | 0.5 | 53 | 97 |
| 2 | 4 | 0.4 | 5 | 30 | 2.4 | 35 | 121 | 1.2 | 35 | 67 |
| 3 | 6 | 0.7 | 3 | 21 | 3.3 | 25 | 73 | 2.1 | 24 | 73 |
| 4 | 8 | 0.9 | 4 | 22 | 4.6 | 29 | 98 | 2.5 | 30 | 145 |
| 5 | 10 | 1.0 | 4 | 31 | 5.9 | 42 | 174 | 3.1 | 56 | 201 |
| 6 | 15 | 1.5 | 13 | 87 | 8.6 | 94 | 951 | 4.8 | 101 | 982 |
| 7 | 20 | 1.9 | 20 | 167 | 11.9 | 162 | 1339 | 5.5 | 191 | 1294 |
| 8 | 30 | 2.8 | 76 | 368 | 15.2 | 816 | 1690 | 8.4 | 784 | 1848 |
| 9 | 60 | 3.0 | 55 | 80 | 15.0 | 2439 | 3287 | 7.5 | 2474 | 3568 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 11.3 % | 43.9 % | 461 | 0.2 % | 0.3 % | 432 | 0.4 % | 0.5 % | 42 |
| 2 | 4 | 15.0 % | 49.4 % | 451 | 0.8 % | 8.6 % | 441 | 0.6 % | 0.9 % | 42 |
| 3 | 6 | 17.9 % | 52.9 % | 451 | 2.5 % | 29.9 % | 436 | 0.8 % | 1.1 % | 43 |
| 4 | 8 | 25.8 % | 134.1 % | 455 | 4.7 % | 36.6 % | 432 | 1.2 % | 2.5 % | 43 |
| 5 | 10 | 33.8 % | 61.1 % | 452 | 1.0 % | 11.6 % | 432 | 1.5 % | 2.2 % | 43 |
| 6 | 15 | 83.1 % | 180.0 % | 456 | 2.7 % | 22.9 % | 444 | 2.7 % | 4.4 % | 43 |
| 7 | 20 | 130.6 % | 203.4 % | 470 | 7.0 % | 57.0 % | 443 | 3.8 % | 5.8 % | 44 |
| 8 | 30 | 182.1 % | 207.5 % | 463 | 3.5 % | 26.1 % | 443 | 4.5 % | 5.4 % | 45 |
| 9 | 60 | 203.5 % | 209.4 % | 486 | 4.9 % | 59.6 % | 444 | 4.2 % | 5.8 % | 47 |

## Corrida `dos_procesos_r3`

2 procesos, 2 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 11.77 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 18:00:25.

Punto de degradación: escalón 9, 60 usuarios (p95 de 3032 ms; 28.4 peticiones por segundo de 60 ofrecidas). Capacidad dentro del objetivo: 30.0 peticiones por segundo con 30 usuarios (p95 de 266 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 102 | 2.0 | 2.9 | 51 | 70 | 87 | 87 | 0.00 % | 11 % y 43 % | 461 |
| 2 | 4 | 200 | 4.0 | 6.1 | 20 | 57 | 71 | 163 | 0.00 % | 8 % y 14 % | 453 |
| 3 | 6 | 300 | 6.0 | 9.5 | 32 | 53 | 80 | 87 | 0.00 % | 12 % y 21 % | 453 |
| 4 | 8 | 400 | 8.0 | 12.2 | 42 | 89 | 141 | 200 | 0.00 % | 23 % y 46 % | 453 |
| 5 | 10 | 500 | 10.0 | 15.1 | 27 | 60 | 82 | 123 | 0.00 % | 22 % y 31 % | 463 |
| 6 | 15 | 750 | 15.0 | 23.2 | 37 | 113 | 183 | 255 | 0.00 % | 37 % y 76 % | 466 |
| 7 | 20 | 1,000 | 20.0 | 29.2 | 44 | 146 | 242 | 428 | 0.00 % | 55 % y 138 % | 455 |
| 8 | 30 | 1,500 | 30.0 | 46.0 | 73 | 266 | 446 | 601 | 0.00 % | 95 % y 139 % | 458 |
| 9 | 60 | 1,420 | 28.4 | 42.1 | 2064 | 3032 (sobre el objetivo) | 3512 | 4103 | 0.00 % | 203 % y 207 % | 475 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 13 | 22 | 1.3 | 53 | 70 | 0.5 | 51 | 75 |
| 2 | 4 | 0.4 | 4 | 16 | 2.4 | 24 | 54 | 1.2 | 21 | 64 |
| 3 | 6 | 0.7 | 9 | 21 | 3.3 | 34 | 57 | 2.1 | 34 | 53 |
| 4 | 8 | 0.9 | 9 | 18 | 4.6 | 43 | 86 | 2.5 | 45 | 120 |
| 5 | 10 | 1.0 | 4 | 17 | 5.9 | 38 | 63 | 3.1 | 40 | 63 |
| 6 | 15 | 1.5 | 7 | 23 | 8.6 | 38 | 113 | 4.9 | 39 | 130 |
| 7 | 20 | 2.0 | 10 | 27 | 12.3 | 46 | 146 | 5.6 | 49 | 168 |
| 8 | 30 | 3.1 | 15 | 44 | 17.4 | 80 | 265 | 9.5 | 86 | 278 |
| 9 | 60 | 3.1 | 80 | 796 | 16.9 | 2162 | 2996 | 8.4 | 2212 | 3156 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 10.6 % | 42.7 % | 461 | 2.4 % | 34.5 % | 404 | 0.3 % | 0.5 % | 42 |
| 2 | 4 | 8.2 % | 14.3 % | 453 | 3.9 % | 28.2 % | 404 | 0.6 % | 1.0 % | 42 |
| 3 | 6 | 11.6 % | 21.2 % | 453 | 2.6 % | 21.3 % | 418 | 0.7 % | 0.9 % | 42 |
| 4 | 8 | 22.6 % | 46.3 % | 453 | 1.7 % | 22.1 % | 418 | 0.9 % | 1.5 % | 43 |
| 5 | 10 | 22.1 % | 31.3 % | 463 | 0.9 % | 10.5 % | 404 | 1.1 % | 1.2 % | 43 |
| 6 | 15 | 36.6 % | 76.0 % | 466 | 1.7 % | 23.0 % | 405 | 1.4 % | 1.9 % | 43 |
| 7 | 20 | 54.7 % | 138.5 % | 455 | 1.9 % | 25.5 % | 405 | 1.7 % | 2.6 % | 44 |
| 8 | 30 | 94.5 % | 139.1 % | 458 | 0.2 % | 0.2 % | 404 | 2.5 % | 3.2 % | 44 |
| 9 | 60 | 203.3 % | 207.1 % | 475 | 2.0 % | 25.6 % | 416 | 4.5 % | 6.0 % | 46 |

## Corrida `dos_procesos_en_serie`

2 procesos, 2 CPU, 1 petición a la vez por proceso y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 22.3 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 15:15:50.

Punto de degradación: escalón 9, 60 usuarios (p95 de 1023 ms). Capacidad dentro del objetivo: 30.0 peticiones por segundo con 30 usuarios (p95 de 102 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 100 | 2.0 | 2.8 | 30 | 73 | 152 | 153 | 0.00 % | 7 % y 32 % | 463 |
| 2 | 4 | 200 | 4.0 | 6.1 | 41 | 111 | 141 | 155 | 0.00 % | 18 % y 66 % | 464 |
| 3 | 6 | 300 | 6.0 | 9.5 | 47 | 148 | 204 | 251 | 0.00 % | 24 % y 77 % | 463 |
| 4 | 8 | 400 | 8.0 | 12.3 | 33 | 53 | 69 | 125 | 0.00 % | 16 % y 23 % | 453 |
| 5 | 10 | 500 | 10.0 | 15.2 | 32 | 54 | 65 | 70 | 0.00 % | 17 % y 22 % | 453 |
| 6 | 15 | 750 | 15.0 | 23.2 | 28 | 50 | 64 | 344 | 0.00 % | 26 % y 50 % | 463 |
| 7 | 20 | 1,000 | 20.0 | 29.3 | 34 | 79 | 113 | 176 | 0.00 % | 32 % y 56 % | 454 |
| 8 | 30 | 1,500 | 30.0 | 46.0 | 42 | 102 | 119 | 126 | 0.00 % | 45 % y 92 % | 454 |
| 9 | 60 | 2,964 | 59.3 | 89.0 | 408 | 1023 (sobre el objetivo) | 1312 | 1414 | 0.00 % | 131 % y 179 % | 454 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 22 | 31 | 1.3 | 33 | 73 | 0.5 | 30 | 90 |
| 2 | 4 | 0.4 | 11 | 79 | 2.4 | 48 | 110 | 1.2 | 44 | 115 |
| 3 | 6 | 0.7 | 23 | 70 | 3.3 | 50 | 148 | 2.1 | 52 | 159 |
| 4 | 8 | 0.9 | 19 | 36 | 4.6 | 34 | 53 | 2.6 | 33 | 60 |
| 5 | 10 | 1.0 | 20 | 38 | 5.9 | 34 | 55 | 3.1 | 32 | 54 |
| 6 | 15 | 1.5 | 16 | 36 | 8.6 | 28 | 50 | 4.9 | 29 | 55 |
| 7 | 20 | 2.0 | 20 | 56 | 12.3 | 35 | 79 | 5.7 | 36 | 82 |
| 8 | 30 | 3.1 | 30 | 83 | 17.4 | 44 | 104 | 9.5 | 43 | 101 |
| 9 | 60 | 6.1 | 369 | 1028 | 35.2 | 408 | 1017 | 17.9 | 412 | 1044 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 7.2 % | 32.3 % | 463 | 1.8 % | 23.8 % | 433 | 0.3 % | 0.4 % | 42 |
| 2 | 4 | 18.3 % | 65.8 % | 464 | 4.0 % | 43.7 % | 442 | 0.8 % | 1.0 % | 42 |
| 3 | 6 | 23.9 % | 76.8 % | 463 | 2.4 % | 29.2 % | 445 | 1.1 % | 1.8 % | 43 |
| 4 | 8 | 15.6 % | 22.5 % | 453 | 2.3 % | 33.7 % | 433 | 0.9 % | 1.1 % | 43 |
| 5 | 10 | 16.9 % | 22.0 % | 453 | 3.9 % | 31.7 % | 433 | 1.1 % | 1.3 % | 43 |
| 6 | 15 | 25.9 % | 49.5 % | 463 | 0.2 % | 0.2 % | 433 | 1.4 % | 1.6 % | 43 |
| 7 | 20 | 32.4 % | 55.9 % | 454 | 3.4 % | 27.5 % | 433 | 1.8 % | 2.3 % | 44 |
| 8 | 30 | 45.4 % | 92.3 % | 454 | 0.2 % | 0.3 % | 433 | 2.2 % | 2.9 % | 44 |
| 9 | 60 | 130.8 % | 179.1 % | 454 | 4.8 % | 37.8 % | 434 | 5.0 % | 7.6 % | 47 |

Variación frente a sus repeticiones:

| Escalón | Usuarios | Peticiones/s, `dos_procesos_en_serie` | Peticiones/s, `dos_procesos_en_serie_r2` | p95 (ms), `dos_procesos_en_serie` | p95 (ms), `dos_procesos_en_serie_r2` | p95 mayor entre p95 menor |
|---|---|---|---|---|---|---|
| 1 | 2 | 2.0 | 2.0 | 73 | 54 | 1.4 |
| 2 | 4 | 4.0 | 4.0 | 111 | 26 | 4.3 |
| 3 | 6 | 6.0 | 6.0 | 148 | 26 | 5.6 |
| 4 | 8 | 8.0 | 8.0 | 53 | 36 | 1.5 |
| 5 | 10 | 10.0 | 10.0 | 54 | 39 | 1.4 |
| 6 | 15 | 15.0 | 15.0 | 50 | 56 | 1.1 |
| 7 | 20 | 20.0 | 20.0 | 79 | 73 | 1.1 |
| 8 | 30 | 30.0 | 30.0 | 102 | 182 | 1.8 |
| 9 | 60 | 59.3 | 60.0 | 1023 | 391 | 2.6 |

## Corrida `dos_procesos_en_serie_r2`

2 procesos, 2 CPU, 1 petición a la vez por proceso y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 20.74 s; escalones de 60 s con 10 s de calentamiento descartados; lotes de 3 estaciones; fecha 2026-11-18 17:28:18.

Ningún escalón rompe el objetivo; el de mayor rendimiento atiende 60.0 peticiones por segundo.

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 100 | 2.0 | 2.8 | 23 | 54 | 71 | 78 | 0.00 % | 8 % y 43 % | 452 |
| 2 | 4 | 200 | 4.0 | 6.1 | 17 | 26 | 34 | 37 | 0.00 % | 8 % y 16 % | 452 |
| 3 | 6 | 300 | 6.0 | 9.5 | 16 | 26 | 50 | 135 | 0.00 % | 12 % y 26 % | 465 |
| 4 | 8 | 400 | 8.0 | 12.2 | 17 | 36 | 48 | 198 | 0.00 % | 17 % y 38 % | 452 |
| 5 | 10 | 500 | 10.0 | 15.1 | 17 | 39 | 71 | 122 | 0.00 % | 17 % y 36 % | 452 |
| 6 | 15 | 750 | 15.0 | 23.2 | 21 | 56 | 66 | 78 | 0.00 % | 27 % y 56 % | 452 |
| 7 | 20 | 1,000 | 20.0 | 29.2 | 28 | 73 | 95 | 124 | 0.00 % | 34 % y 72 % | 452 |
| 8 | 30 | 1,500 | 30.0 | 46.0 | 54 | 182 | 286 | 334 | 0.00 % | 51 % y 79 % | 452 |
| 9 | 60 | 3,000 | 60.0 | 90.4 | 215 | 391 | 554 | 878 | 0.00 % | 111 % y 137 % | 453 |

| Escalón | Usuarios | `/health` por segundo | `/health` p50 (ms) | `/health` p95 (ms) | `/predecir` por segundo | `/predecir` p50 (ms) | `/predecir` p95 (ms) | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0.2 | 3 | 5 | 1.3 | 24 | 55 | 0.5 | 22 | 45 |
| 2 | 4 | 0.4 | 3 | 3 | 2.4 | 18 | 26 | 1.2 | 18 | 33 |
| 3 | 6 | 0.7 | 3 | 4 | 3.3 | 18 | 28 | 2.1 | 16 | 24 |
| 4 | 8 | 0.9 | 3 | 4 | 4.6 | 19 | 36 | 2.5 | 17 | 36 |
| 5 | 10 | 1.0 | 3 | 17 | 5.9 | 18 | 37 | 3.1 | 19 | 44 |
| 6 | 15 | 1.5 | 4 | 38 | 8.6 | 23 | 56 | 4.9 | 22 | 56 |
| 7 | 20 | 2.0 | 15 | 57 | 12.3 | 30 | 73 | 5.6 | 28 | 82 |
| 8 | 30 | 3.1 | 35 | 172 | 17.4 | 56 | 183 | 9.5 | 56 | 181 |
| 9 | 60 | 6.2 | 196 | 390 | 35.5 | 218 | 391 | 18.3 | 211 | 396 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 7.6 % | 42.6 % | 452 | 0.3 % | 0.4 % | 404 | 0.4 % | 0.7 % | 42 |
| 2 | 4 | 8.0 % | 15.8 % | 452 | 1.9 % | 26.3 % | 417 | 0.6 % | 0.8 % | 42 |
| 3 | 6 | 12.0 % | 26.0 % | 465 | 1.5 % | 13.7 % | 414 | 0.7 % | 0.8 % | 42 |
| 4 | 8 | 16.8 % | 38.4 % | 452 | 3.5 % | 25.4 % | 404 | 1.0 % | 1.6 % | 43 |
| 5 | 10 | 17.5 % | 35.9 % | 452 | 5.6 % | 59.4 % | 404 | 1.1 % | 1.5 % | 43 |
| 6 | 15 | 27.4 % | 56.2 % | 452 | 4.2 % | 33.5 % | 404 | 1.3 % | 1.4 % | 43 |
| 7 | 20 | 34.3 % | 71.8 % | 452 | 2.1 % | 28.5 % | 404 | 1.6 % | 1.9 % | 43 |
| 8 | 30 | 50.9 % | 78.6 % | 452 | 2.1 % | 31.3 % | 404 | 2.2 % | 2.9 % | 44 |
| 9 | 60 | 111.0 % | 136.6 % | 453 | 3.5 % | 42.8 % | 413 | 3.9 % | 6.6 % | 46 |

## Corrida `lote_hora`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 18.98 s; escalones de 45 s con 10 s de calentamiento descartados; lotes de 472 estaciones; fecha 2026-11-18 14:26:51.

Punto de degradación: escalón 4, 8 usuarios (p95 de 1912 ms; 6.8 peticiones por segundo de 8 ofrecidas). Capacidad dentro del objetivo: 4.0 peticiones por segundo con 4 usuarios (p95 de 149 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 36 | 1.0 | 485.5 | 40 | 101 | 131 | 131 | 0.00 % | 7 % y 32 % | 221 |
| 2 | 2 | 70 | 2.0 | 944.0 | 37 | 65 | 73 | 73 | 0.00 % | 11 % y 45 % | 217 |
| 3 | 4 | 140 | 4.0 | 1888.0 | 76 | 149 | 287 | 294 | 0.00 % | 20 % y 28 % | 218 |
| 4 | 8 | 239 | 6.8 | 3223.1 | 894 | 1912 (sobre el objetivo) | 2389 | 2531 | 0.00 % | 95 % y 106 % | 240 |
| 5 | 12 | 232 | 6.6 | 3128.7 | 1717 | 2546 (sobre el objetivo) | 2999 | 3044 | 0.00 % | 101 % y 103 % | 252 |

| Escalón | Usuarios | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|
| 1 | 1 | 1.0 | 40 | 101 |
| 2 | 2 | 2.0 | 37 | 65 |
| 3 | 4 | 4.0 | 76 | 149 |
| 4 | 8 | 6.8 | 894 | 1912 |
| 5 | 12 | 6.6 | 1717 | 2546 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 7.2 % | 32.4 % | 221 | 3.8 % | 39.2 % | 431 | 0.5 % | 0.6 % | 43 |
| 2 | 2 | 10.9 % | 44.8 % | 217 | 2.1 % | 20.4 % | 441 | 0.8 % | 1.2 % | 43 |
| 3 | 4 | 20.2 % | 27.9 % | 218 | 1.4 % | 12.3 % | 432 | 1.5 % | 1.9 % | 44 |
| 4 | 8 | 94.8 % | 106.4 % | 240 | 3.6 % | 33.3 % | 431 | 4.4 % | 4.7 % | 46 |
| 5 | 12 | 100.8 % | 102.9 % | 252 | 8.5 % | 49.2 % | 445 | 4.2 % | 5.9 % | 47 |

Variación frente a sus repeticiones:

| Escalón | Usuarios | Peticiones/s, `lote_hora` | Peticiones/s, `lote_hora_r2` | Peticiones/s, `lote_hora_r3` | p95 (ms), `lote_hora` | p95 (ms), `lote_hora_r2` | p95 (ms), `lote_hora_r3` | p95 mayor entre p95 menor |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1.0 | 1.0 | 1.0 | 101 | 83 | 54 | 1.9 |
| 2 | 2 | 2.0 | 2.0 | 2.0 | 65 | 162 | 51 | 3.2 |
| 3 | 4 | 4.0 | 4.0 | 4.0 | 149 | 463 | 66 | 7.0 |
| 4 | 8 | 6.8 | 8.0 | 8.0 | 1912 | 320 | 219 | 8.7 |
| 5 | 12 | 6.6 | 8.6 | 12.0 | 2546 | 1881 | 770 | 3.3 |

## Corrida `lote_hora_r2`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 30.9 s; escalones de 45 s con 10 s de calentamiento descartados; lotes de 472 estaciones; fecha 2026-11-18 14:51:30.

Punto de degradación: escalón 5, 12 usuarios (p95 de 1881 ms; 8.6 peticiones por segundo de 12 ofrecidas). Capacidad dentro del objetivo: 8.0 peticiones por segundo con 8 usuarios (p95 de 320 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 36 | 1.0 | 485.5 | 49 | 83 | 110 | 110 | 0.00 % | 12 % y 43 % | 218 |
| 2 | 2 | 70 | 2.0 | 944.0 | 61 | 162 | 239 | 239 | 0.00 % | 22 % y 49 % | 217 |
| 3 | 4 | 140 | 4.0 | 1888.0 | 106 | 463 | 657 | 658 | 0.00 % | 31 % y 53 % | 227 |
| 4 | 8 | 280 | 8.0 | 3776.0 | 47 | 320 | 657 | 688 | 0.00 % | 55 % y 105 % | 228 |
| 5 | 12 | 302 | 8.6 | 4072.7 | 1356 | 1881 (sobre el objetivo) | 2497 | 2723 | 0.00 % | 101 % y 102 % | 239 |

| Escalón | Usuarios | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|
| 1 | 1 | 1.0 | 49 | 83 |
| 2 | 2 | 2.0 | 61 | 162 |
| 3 | 4 | 4.0 | 106 | 463 |
| 4 | 8 | 8.0 | 47 | 320 |
| 5 | 12 | 8.6 | 1356 | 1881 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 11.7 % | 42.7 % | 218 | 13.3 % | 103.0 % | 432 | 0.6 % | 0.8 % | 43 |
| 2 | 2 | 22.3 % | 48.9 % | 217 | 1.4 % | 10.9 % | 434 | 1.2 % | 1.9 % | 43 |
| 3 | 4 | 30.8 % | 53.1 % | 227 | 2.8 % | 17.4 % | 442 | 2.0 % | 3.2 % | 44 |
| 4 | 8 | 54.6 % | 105.4 % | 228 | 0.2 % | 0.3 % | 432 | 3.5 % | 4.3 % | 45 |
| 5 | 12 | 101.1 % | 102.2 % | 239 | 5.3 % | 51.0 % | 432 | 4.3 % | 5.2 % | 47 |

## Corrida `lote_hora_r3`

1 proceso, 1 CPU y 1g de memoria; modelo `mibici-equipo38-p2-riesgo` versión 1 (alias `champion`); arranque del servicio en 13.33 s; escalones de 45 s con 10 s de calentamiento descartados; lotes de 472 estaciones; fecha 2026-11-18 17:37:44.

Punto de degradación: escalón 5, 12 usuarios (p95 de 770 ms). Capacidad dentro del objetivo: 8.0 peticiones por segundo con 8 usuarios (p95 de 219 ms).

| Escalón | Usuarios | Peticiones medidas | Peticiones/s | Predicciones/s | p50 (ms) | p95 (ms) | p99 (ms) | Máximo (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 35 | 1.0 | 472.0 | 30 | 54 | 59 | 59 | 0.00 % | 6 % y 27 % | 218 |
| 2 | 2 | 70 | 2.0 | 944.0 | 31 | 51 | 63 | 63 | 0.00 % | 12 % y 33 % | 218 |
| 3 | 4 | 140 | 4.0 | 1888.0 | 48 | 66 | 76 | 115 | 0.00 % | 13 % y 31 % | 219 |
| 4 | 8 | 280 | 8.0 | 3776.0 | 119 | 219 | 388 | 403 | 0.00 % | 37 % y 59 % | 236 |
| 5 | 12 | 420 | 12.0 | 5664.0 | 177 | 770 (sobre el objetivo) | 927 | 1001 | 0.00 % | 64 % y 102 % | 239 |

| Escalón | Usuarios | `/predecir/lote` por segundo | `/predecir/lote` p50 (ms) | `/predecir/lote` p95 (ms) |
|---|---|---|---|---|
| 1 | 1 | 1.0 | 30 | 54 |
| 2 | 2 | 2.0 | 31 | 51 |
| 3 | 4 | 4.0 | 48 | 66 |
| 4 | 8 | 8.0 | 119 | 219 |
| 5 | 12 | 12.0 | 177 | 770 |

| Escalón | Usuarios | api, CPU media | api, CPU máxima | api, memoria máxima (MiB) | mlflow, CPU media | mlflow, CPU máxima | mlflow, memoria máxima (MiB) | locust, CPU media | locust, CPU máxima | locust, memoria máxima (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 6.0 % | 26.9 % | 218 | 1.8 % | 17.3 % | 404 | 0.5 % | 0.8 % | 43 |
| 2 | 2 | 11.7 % | 33.3 % | 218 | 0.2 % | 0.3 % | 404 | 0.8 % | 1.0 % | 43 |
| 3 | 4 | 13.5 % | 31.0 % | 219 | 0.2 % | 0.2 % | 404 | 1.3 % | 1.7 % | 44 |
| 4 | 8 | 37.0 % | 59.2 % | 236 | 6.6 % | 45.0 % | 404 | 2.5 % | 3.3 % | 44 |
| 5 | 12 | 64.4 % | 102.1 % | 239 | 3.8 % | 36.3 % | 404 | 4.0 % | 5.5 % | 47 |
