# Costo por inferencia del servicio de predicción

Generado el 2026-11-18 18:20:35 con `python -m mibici.finops.costo` a partir de los CSV de `reports/carga/`. Objetivo de servicio: p95 de hasta 500 ms y errores de hasta 1.0 %. Demanda de la operación: 472 predicciones por hora. Los precios son por hora de instancia, en dólares, y llegan como parámetro.

## Capacidad dentro del objetivo

Escalón de mayor rendimiento de cada corrida antes del primero que rompe el objetivo, con la CPU y la memoria del servicio en ese escalón.

| Corrida | Procesos | CPU | Peticiones a la vez por proceso | Usuarios | Peticiones/s | Peticiones de predicción/s | Predicciones/s | p50 (ms) | p95 (ms) | Errores | CPU del servicio, media y máxima | Memoria máxima del servicio (MiB) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `un_proceso` | 1 | 1 | 40 | 8 | 8.0 | 7.1 | 12.1 | 42 | 458 | 0.00 % | 39 % y 99 % | 231 |
| `un_proceso_r2` | 1 | 1 | 40 | 10 | 10.0 | 9.0 | 15.1 | 37 | 77 | 0.00 % | 20 % y 24 % | 218 |
| `un_proceso_r3` | 1 | 1 | 40 | 15 | 15.0 | 13.5 | 23.2 | 65 | 271 | 0.00 % | 44 % y 80 % | 230 |
| `un_proceso_r4` | 1 | 1 | 40 | 10 | 10.0 | 9.0 | 15.1 | 35 | 255 | 0.00 % | 34 % y 100 % | 223 |
| `un_proceso_r5` | 1 | 1 | 40 | 15 | 15.0 | 13.5 | 23.2 | 65 | 241 | 0.00 % | 46 % y 74 % | 235 |
| `un_proceso_en_serie` | 1 | 1 | 1 | 20 | 20.0 | 18.0 | 29.2 | 52 | 108 | 0.00 % | 37 % y 56 % | 218 |
| `un_proceso_en_serie_r2` | 1 | 1 | 1 | 30 | 30.0 | 26.9 | 46.0 | 67 | 228 | 0.00 % | 42 % y 75 % | 218 |
| `un_proceso_en_serie_r3` | 1 | 1 | 1 | 30 | 30.0 | 26.9 | 46.0 | 117 | 313 | 0.00 % | 58 % y 98 % | 229 |
| `un_proceso_en_serie_r4` | 1 | 1 | 1 | 30 | 30.0 | 26.9 | 46.0 | 85 | 202 | 0.00 % | 49 % y 76 % | 218 |
| `dos_procesos_un_cpu` | 2 | 1 | 40 | 10 | 10.0 | 9.0 | 15.1 | 20 | 72 | 0.00 % | 20 % y 43 % | 451 |
| `dos_procesos_un_cpu_r2` | 2 | 1 | 40 | 15 | 15.1 | 13.6 | 23.4 | 36 | 450 | 0.00 % | 48 % y 87 % | 465 |
| `dos_procesos` | 2 | 2 | 40 | 15 | 15.0 | 13.5 | 23.3 | 34 | 148 | 0.00 % | 50 % y 80 % | 467 |
| `dos_procesos_r2` | 2 | 2 | 40 | 10 | 10.0 | 9.0 | 15.1 | 39 | 182 | 0.00 % | 34 % y 61 % | 452 |
| `dos_procesos_r3` | 2 | 2 | 40 | 30 | 30.0 | 26.9 | 46.0 | 73 | 266 | 0.00 % | 95 % y 139 % | 458 |
| `dos_procesos_en_serie` | 2 | 2 | 1 | 30 | 30.0 | 26.9 | 46.0 | 42 | 102 | 0.00 % | 45 % y 92 % | 454 |
| `dos_procesos_en_serie_r2` | 2 | 2 | 1 | 60 | 60.0 | 53.8 | 90.4 | 215 | 391 | 0.00 % | 111 % y 137 % | 453 |
| `lote_hora` | 1 | 1 | 40 | 4 | 4.0 | 4.0 | 1888.0 | 76 | 149 | 0.00 % | 20 % y 28 % | 218 |
| `lote_hora_r2` | 1 | 1 | 40 | 8 | 8.0 | 8.0 | 3776.0 | 47 | 320 | 0.00 % | 55 % y 105 % | 228 |
| `lote_hora_r3` | 1 | 1 | 40 | 8 | 8.0 | 8.0 | 3776.0 | 119 | 219 | 0.00 % | 37 % y 59 % | 236 |

Predicciones por segundo que cada corrida sostiene según el objetivo de p95:

| Corrida | p95 de hasta 250 ms | p95 de hasta 500 ms | p95 de hasta 1000 ms | p95 de hasta 2000 ms |
|---|---|---|---|---|
| `un_proceso` | 2.9 | 12.1 | 12.1 | 14.8 |
| `un_proceso_r2` | 15.1 | 15.1 | 22.8 | 26.3 |
| `un_proceso_r3` | 15.1 | 23.2 | 23.2 | 27.1 |
| `un_proceso_r4` | 2.9 | 15.1 | 15.1 | 42.4 |
| `un_proceso_r5` | 23.2 | 23.2 | 23.2 | 33.9 |
| `un_proceso_en_serie` | 29.2 | 29.2 | 29.2 | 44.0 |
| `un_proceso_en_serie_r2` | 46.0 | 46.0 | 46.0 | 82.1 |
| `un_proceso_en_serie_r3` | 9.5 | 46.0 | 46.0 | 69.2 |
| `un_proceso_en_serie_r4` | 46.0 | 46.0 | 46.0 | 79.2 |
| `dos_procesos_un_cpu` | 15.1 | 15.1 | 15.1 | 25.8 |
| `dos_procesos_un_cpu_r2` | 14.6 | 23.4 | 23.4 | 27.3 |
| `dos_procesos` | 23.3 | 23.3 | 23.3 | 28.1 |
| `dos_procesos_r2` | 15.1 | 15.1 | 23.0 | 40.3 |
| `dos_procesos_r3` | 29.2 | 46.0 | 46.0 | 46.0 |
| `dos_procesos_en_serie` | 46.0 | 46.0 | 46.0 | 89.0 |
| `dos_procesos_en_serie_r2` | 46.0 | 90.4 | 90.4 | 90.4 |
| `lote_hora` | 1888.0 | 1888.0 | 1888.0 | 3223.1 |
| `lote_hora_r2` | 944.0 | 3776.0 | 3776.0 | 4072.7 |
| `lote_hora_r3` | 3776.0 | 3776.0 | 5664.0 | 5664.0 |

## Costo a plena capacidad

Costo por inferencia = precio por hora de la instancia / (inferencias por segundo sostenidas dentro del objetivo x 3,600). Una petición de predicción es una llamada a `/predecir` o a `/predecir/lote`; una predicción es una estación en una hora. El sistema cabe en la instancia si la suma de los picos de CPU de sus contenedores no pasa de sus vCPU y la de memoria, con un margen de 30 %, no pasa de su memoria.

| Instancia | USD por hora | Corrida | Peticiones de predicción por hora | USD por millón de peticiones | Predicciones por hora | USD por millón de predicciones | Suma de los picos de CPU (núcleos) | Suma de los picos de memoria (GiB) | Cabe en la instancia |
|---|---|---|---|---|---|---|---|---|---|
| t3.small | 0.0208 | `un_proceso` | 25,704 | 0.8092 | 43,704 | 0.4759 | 1.48 | 0.70 | sí |
| t3.small | 0.0208 | `un_proceso_r2` | 32,256 | 0.6448 | 54,432 | 0.3821 | 0.49 | 0.68 | sí |
| t3.small | 0.0208 | `un_proceso_r3` | 48,600 | 0.4280 | 83,592 | 0.2488 | 0.83 | 0.69 | sí |
| t3.small | 0.0208 | `un_proceso_r4` | 32,256 | 0.6448 | 54,432 | 0.3821 | 1.40 | 0.65 | sí |
| t3.small | 0.0208 | `un_proceso_r5` | 48,600 | 0.4280 | 83,592 | 0.2488 | 0.92 | 0.67 | sí |
| t3.small | 0.0208 | `un_proceso_en_serie` | 64,656 | 0.3217 | 105,264 | 0.1976 | 0.85 | 0.68 | sí |
| t3.small | 0.0208 | `un_proceso_en_serie_r2` | 96,984 | 0.2145 | 165,672 | 0.1255 | 0.78 | 0.68 | sí |
| t3.small | 0.0208 | `un_proceso_en_serie_r3` | 96,984 | 0.2145 | 165,672 | 0.1255 | 1.40 | 0.67 | sí |
| t3.small | 0.0208 | `un_proceso_en_serie_r4` | 96,984 | 0.2145 | 165,672 | 0.1255 | 1.03 | 0.66 | sí |
| t3.small | 0.0208 | `dos_procesos_un_cpu` | 32,256 | 0.6448 | 54,432 | 0.3821 | 0.74 | 0.91 | sí |
| t3.small | 0.0208 | `dos_procesos_un_cpu_r2` | 48,888 | 0.4255 | 84,168 | 0.2471 | 1.28 | 0.89 | sí |
| t3.small | 0.0208 | `dos_procesos` | 48,672 | 0.4274 | 83,808 | 0.2482 | 0.83 | 0.92 | sí |
| t3.small | 0.0208 | `dos_procesos_r2` | 32,328 | 0.6434 | 54,504 | 0.3816 | 0.75 | 0.91 | sí |
| t3.small | 0.0208 | `dos_procesos_r3` | 96,984 | 0.2145 | 165,672 | 0.1255 | 1.43 | 0.89 | sí |
| t3.small | 0.0208 | `dos_procesos_en_serie` | 96,984 | 0.2145 | 165,672 | 0.1255 | 0.96 | 0.91 | sí |
| t3.small | 0.0208 | `dos_procesos_en_serie_r2` | 193,752 | 0.1074 | 325,368 | 0.0639 | 1.86 | 0.89 | sí |
| t3.small | 0.0208 | `lote_hora` | 14,400 | 1.4444 | 6,796,800 | 0.0031 | 0.42 | 0.68 | sí |
| t3.small | 0.0208 | `lote_hora_r2` | 28,800 | 0.7222 | 13,593,600 | 0.0015 | 1.10 | 0.69 | sí |
| t3.small | 0.0208 | `lote_hora_r3` | 28,800 | 0.7222 | 13,593,600 | 0.0015 | 1.08 | 0.67 | sí |
| c6a.large | 0.0765 | `un_proceso` | 25,704 | 2.9762 | 43,704 | 1.7504 | 1.48 | 0.70 | sí |
| c6a.large | 0.0765 | `un_proceso_r2` | 32,256 | 2.3717 | 54,432 | 1.4054 | 0.49 | 0.68 | sí |
| c6a.large | 0.0765 | `un_proceso_r3` | 48,600 | 1.5741 | 83,592 | 0.9152 | 0.83 | 0.69 | sí |
| c6a.large | 0.0765 | `un_proceso_r4` | 32,256 | 2.3717 | 54,432 | 1.4054 | 1.40 | 0.65 | sí |
| c6a.large | 0.0765 | `un_proceso_r5` | 48,600 | 1.5741 | 83,592 | 0.9152 | 0.92 | 0.67 | sí |
| c6a.large | 0.0765 | `un_proceso_en_serie` | 64,656 | 1.1832 | 105,264 | 0.7267 | 0.85 | 0.68 | sí |
| c6a.large | 0.0765 | `un_proceso_en_serie_r2` | 96,984 | 0.7888 | 165,672 | 0.4618 | 0.78 | 0.68 | sí |
| c6a.large | 0.0765 | `un_proceso_en_serie_r3` | 96,984 | 0.7888 | 165,672 | 0.4618 | 1.40 | 0.67 | sí |
| c6a.large | 0.0765 | `un_proceso_en_serie_r4` | 96,984 | 0.7888 | 165,672 | 0.4618 | 1.03 | 0.66 | sí |
| c6a.large | 0.0765 | `dos_procesos_un_cpu` | 32,256 | 2.3717 | 54,432 | 1.4054 | 0.74 | 0.91 | sí |
| c6a.large | 0.0765 | `dos_procesos_un_cpu_r2` | 48,888 | 1.5648 | 84,168 | 0.9089 | 1.28 | 0.89 | sí |
| c6a.large | 0.0765 | `dos_procesos` | 48,672 | 1.5717 | 83,808 | 0.9128 | 0.83 | 0.92 | sí |
| c6a.large | 0.0765 | `dos_procesos_r2` | 32,328 | 2.3664 | 54,504 | 1.4036 | 0.75 | 0.91 | sí |
| c6a.large | 0.0765 | `dos_procesos_r3` | 96,984 | 0.7888 | 165,672 | 0.4618 | 1.43 | 0.89 | sí |
| c6a.large | 0.0765 | `dos_procesos_en_serie` | 96,984 | 0.7888 | 165,672 | 0.4618 | 0.96 | 0.91 | sí |
| c6a.large | 0.0765 | `dos_procesos_en_serie_r2` | 193,752 | 0.3948 | 325,368 | 0.2351 | 1.86 | 0.89 | sí |
| c6a.large | 0.0765 | `lote_hora` | 14,400 | 5.3125 | 6,796,800 | 0.0113 | 0.42 | 0.68 | sí |
| c6a.large | 0.0765 | `lote_hora_r2` | 28,800 | 2.6562 | 13,593,600 | 0.0056 | 1.10 | 0.69 | sí |
| c6a.large | 0.0765 | `lote_hora_r3` | 28,800 | 2.6562 | 13,593,600 | 0.0056 | 1.08 | 0.67 | sí |

## Costo con la demanda real (472 predicciones por hora)

Siempre encendida, la instancia cuesta su precio por hora sin importar cuánto se use: costo por predicción = precio por hora / demanda por hora. El mes tiene 730 horas.

| Instancia | Precio | USD por hora | USD al mes | USD por millón de predicciones |
|---|---|---|---|---|
| t3.small | Bajo demanda | 0.0208 | 15.18 | 44.07 |
| c6a.large | Bajo demanda | 0.0765 | 55.84 | 162.08 |

Encendida solo para atender la demanda de cada hora, la instancia arranca, predice y se apaga: paga (arranque del servicio + demanda / predicciones por segundo) segundos de cada hora.

| Instancia | Corrida | Utilización si quedara siempre encendida | Segundos encendida por hora | USD al mes | USD por millón de predicciones | Ahorro frente a siempre encendida |
|---|---|---|---|---|---|---|
| t3.small | `un_proceso` | 1.080 % | 81.6 | 0.34 | 1.00 | 97.7 % |
| t3.small | `un_proceso_r2` | 0.867 % | 58.8 | 0.25 | 0.72 | 98.4 % |
| t3.small | `un_proceso_r3` | 0.565 % | 43.1 | 0.18 | 0.53 | 98.8 % |
| t3.small | `un_proceso_r4` | 0.867 % | 49.1 | 0.21 | 0.60 | 98.6 % |
| t3.small | `un_proceso_r5` | 0.565 % | 28.9 | 0.12 | 0.35 | 99.2 % |
| t3.small | `un_proceso_en_serie` | 0.448 % | 34.6 | 0.15 | 0.42 | 99.0 % |
| t3.small | `un_proceso_en_serie_r2` | 0.285 % | 22.1 | 0.09 | 0.27 | 99.4 % |
| t3.small | `un_proceso_en_serie_r3` | 0.285 % | 33.2 | 0.14 | 0.41 | 99.1 % |
| t3.small | `un_proceso_en_serie_r4` | 0.285 % | 20.5 | 0.09 | 0.25 | 99.4 % |
| t3.small | `dos_procesos_un_cpu` | 0.867 % | 62.6 | 0.26 | 0.77 | 98.3 % |
| t3.small | `dos_procesos_un_cpu_r2` | 0.561 % | 42.0 | 0.18 | 0.51 | 98.8 % |
| t3.small | `dos_procesos` | 0.563 % | 51.4 | 0.22 | 0.63 | 98.6 % |
| t3.small | `dos_procesos_r2` | 0.866 % | 62.9 | 0.27 | 0.77 | 98.3 % |
| t3.small | `dos_procesos_r3` | 0.285 % | 22.0 | 0.09 | 0.27 | 99.4 % |
| t3.small | `dos_procesos_en_serie` | 0.285 % | 32.6 | 0.14 | 0.40 | 99.1 % |
| t3.small | `dos_procesos_en_serie_r2` | 0.145 % | 26.0 | 0.11 | 0.32 | 99.3 % |
| t3.small | `lote_hora` | 0.007 % | 19.2 | 0.08 | 0.24 | 99.5 % |
| t3.small | `lote_hora_r2` | 0.003 % | 31.0 | 0.13 | 0.38 | 99.1 % |
| t3.small | `lote_hora_r3` | 0.003 % | 13.5 | 0.06 | 0.16 | 99.6 % |
| c6a.large | `un_proceso` | 1.080 % | 81.6 | 1.27 | 3.67 | 97.7 % |
| c6a.large | `un_proceso_r2` | 0.867 % | 58.8 | 0.91 | 2.65 | 98.4 % |
| c6a.large | `un_proceso_r3` | 0.565 % | 43.1 | 0.67 | 1.94 | 98.8 % |
| c6a.large | `un_proceso_r4` | 0.867 % | 49.1 | 0.76 | 2.21 | 98.6 % |
| c6a.large | `un_proceso_r5` | 0.565 % | 28.9 | 0.45 | 1.30 | 99.2 % |
| c6a.large | `un_proceso_en_serie` | 0.448 % | 34.6 | 0.54 | 1.56 | 99.0 % |
| c6a.large | `un_proceso_en_serie_r2` | 0.285 % | 22.1 | 0.34 | 0.99 | 99.4 % |
| c6a.large | `un_proceso_en_serie_r3` | 0.285 % | 33.2 | 0.51 | 1.49 | 99.1 % |
| c6a.large | `un_proceso_en_serie_r4` | 0.285 % | 20.5 | 0.32 | 0.92 | 99.4 % |
| c6a.large | `dos_procesos_un_cpu` | 0.867 % | 62.6 | 0.97 | 2.82 | 98.3 % |
| c6a.large | `dos_procesos_un_cpu_r2` | 0.561 % | 42.0 | 0.65 | 1.89 | 98.8 % |
| c6a.large | `dos_procesos` | 0.563 % | 51.4 | 0.80 | 2.31 | 98.6 % |
| c6a.large | `dos_procesos_r2` | 0.866 % | 62.9 | 0.98 | 2.83 | 98.3 % |
| c6a.large | `dos_procesos_r3` | 0.285 % | 22.0 | 0.34 | 0.99 | 99.4 % |
| c6a.large | `dos_procesos_en_serie` | 0.285 % | 32.6 | 0.51 | 1.47 | 99.1 % |
| c6a.large | `dos_procesos_en_serie_r2` | 0.145 % | 26.0 | 0.40 | 1.17 | 99.3 % |
| c6a.large | `lote_hora` | 0.007 % | 19.2 | 0.30 | 0.87 | 99.5 % |
| c6a.large | `lote_hora_r2` | 0.003 % | 31.0 | 0.48 | 1.40 | 99.1 % |
| c6a.large | `lote_hora_r3` | 0.003 % | 13.5 | 0.21 | 0.61 | 99.6 % |
