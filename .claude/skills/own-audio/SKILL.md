---
name: own-audio
description: Lleva los sonidos y la música PROPIOS del usuario (hechos en su DAW) a un juego de Roblox - revisar nombres y formato de los WAV, normalizar y convertir con ffmpeg, subir por Open Cloud sin repetir subidas y escribir un SoundBank compatible con roblox-sfx. Úsala cuando el usuario diga "mis sonidos", "mi música", "lo grabé yo", "exporté de FL Studio/Ableton/Reaper", cuando haya WAV en games/<Juego>/assets/audio/source/, o cuando pida subir audio propio o meterlo en el SoundBank. NO es para buscar sonidos de la Creator Store: para eso está roblox-sfx.
---

# own-audio

El audio propio tiene tres problemas que esta skill resuelve en orden:

1. Los WAV de un DAW llegan con niveles y canales distintos.
2. El cupo de subida de audio de Open Cloud es pequeño (ver `docs/quotas.md`).
3. El juego no debe tener IDs escritos a mano, sino un SoundBank por roles.

Todo pasa por `scripts/audio.py`. Ejecútalo desde la raíz del repo:

```bash
A=.claude/skills/own-audio/scripts/audio.py
python $A check  --game <Juego>      # nombres, formato y límites; no necesita ffmpeg
python $A build  --game <Juego>      # normaliza y convierte (necesita ffmpeg)
python $A upload --game <Juego>      # simulacro: qué se subiría y cuánto cupo gasta
python $A upload --game <Juego> --yes
python $A bank   --game <Juego> [--merge games/<Juego>/work/manifest.json]
```

`<Juego>` es el nombre de la carpeta dentro de `ROBLOX_GAMES_HOME` (o una ruta).

## Entrada y convenciones

- **Entrada:** WAV en `games/<Juego>/assets/audio/source/`. Son los masters; nunca se modifican.
- **Nombre:** `categoria_nombre_variante`, en minúsculas, con guiones dentro de cada
  parte. Ejemplos: `sfx_coin-pickup_01`, `ui_click_soft`, `music_lobby_main`,
  `amb_forest_night`. El nombre del archivo es el **rol** en el SoundBank, así que
  renombrar un archivo rompe el código que usa ese rol.
- **Canales:**
  - `music`, `amb` y `ui` quedan en **estéreo**: se oyen "dentro de la cabeza".
  - Todo lo demás (`sfx`, `foot`, `weapon`, etc.) queda en **mono**, porque Roblox solo posiciona en 3D un sonido mono.
  - Si un efecto 3D viene en estéreo, `check` lo avisa y `build` lo pasa a mono. Pide al usuario que revise la mezcla si el efecto depende del estéreo.
- **Niveles** (convención de la casa, no regla de Roblox):
  - `music` a −16 LUFS y `amb` a −20 LUFS, con normalización EBU R128 en dos pasadas y techo de −1 dBTP.
  - Los sonidos cortos (menos de 3 s, o de cualquier otra categoría) se normalizan al pico de −1 dBFS: con tan poca duración, la sonoridad integrada no significa nada.
- **Salida de build:** OGG Vorbis (calidad 6) a 48 kHz en `assets/audio/build/`.

## Requisitos de Roblox

Verificados el 2026-10-11 en la documentación oficial. Las cifras y sus fuentes están en `docs/quotas.md`.

- Formatos `.mp3`, `.ogg`, `.wav` o `.flac`, de una sola pista.
- **Menos de 7 minutos** y **menos de 20 MB**, a 48 kHz o menos, mono o estéreo.
- Un audio subido **no se puede actualizar**: cada cambio es una subida nueva y gasta cupo.
- **Cupo:** las dos páginas oficiales no coinciden (100 al mes o 2.000 cada 30 días con ID
  verificado). `quota-guard` usa la cifra conservadora.

`build` falla si un archivo convertido se pasa de esos límites.

## Procedimiento

1. **`check`.** Corrige con el usuario los nombres o archivos marcados con `!!`.
2. **`build`.** Si falta ffmpeg, el script sale con código 3 y dice cómo instalarlo
   (`winget install Gyan.FFmpeg`, `brew install ffmpeg` o `sudo apt install ffmpeg`).
   Pregunta antes de instalar nada. Lo que no cambió (mismo hash y misma receta) no se reconstruye.
3. **`upload` sin `--yes`.** Muestra la lista y llama a `quota.py estimate opencloud-audio`.
   - Sigue la skill `quota-guard`: di al usuario cuántas subidas son y cuánto cupo queda, y **espera su aprobación**.
   - Si `estimate` sale con 2, no subas: ofrece subir menos archivos o esperar.
4. **`upload --yes`.** Necesita `ROBLOX_API_KEY` (Open Cloud con permiso de Assets) y `ROBLOX_USER_ID` o `ROBLOX_GROUP_ID`.
   - Nunca pidas esos valores en el chat: si faltan, explica cómo ponerlos con `setx` / `export`.
   - **Caché por hash:** un archivo cuyo contenido no cambió desde su última subida no se vuelve a subir.
   - Cada subida correcta se guarda enseguida en `audio.lock.json` y se registra en el registro de cupos.
5. **`bank`.** Escribe `SoundBank.luau` y `Sfx.luau` en `assets/audio/bank/`.
   - Cópialos a `src/shared/Config/SoundBank.luau` y `src/shared/Sfx.luau` del juego.
   - Con `--merge` se mezclan los sonidos de la Creator Store que eligió `roblox-sfx`, desde su `manifest.json`.
   - El formato es el de `roblox-sfx`: el script importa su `emit_bank.py`, así que `Sfx.play("sfx_coin-pickup_01")` funciona igual con los dos bancos.
6. **Haz commit** de `assets/audio/audio.lock.json` en el repo del juego. Ahí viven los IDs y
   los hashes que evitan resubidas. `build/` y `bank/` se pueden regenerar.

## Qué no hacer

- No pongas IDs de audio a mano en el código: siempre por rol, a través de `Sfx`.
- No subas audio de terceros con esta skill: para eso están la Creator Store y `roblox-sfx`.
- No edites `SoundBank.luau` a mano: vuelve a ejecutar `bank`.
