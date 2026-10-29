---
name: own-images
description: Sube las imágenes PROPIAS del usuario (iconos, decals, arte de UI, logos en PNG/SVG/JPG) a Roblox con Asphalt - revisa nombres y tamaños, sube por Open Cloud sin repetir subidas (lockfile por hash) y genera un módulo Luau con los IDs para no escribirlos a mano. Úsala cuando el usuario diga "mis imágenes", "mis iconos", "sube el logo", "tengo los PNG de la UI", cuando haya archivos en games/<Juego>/assets/images/, o cuando haga falta el ID de una imagen propia en el código. NO es para audio (eso es own-audio) ni para generar imágenes (eso es roblox-ui / roblox-texture-gen).
---

# own-images

Lleva las imágenes propias a Roblox con [Asphalt](https://github.com/jackTabsCode/asphalt) (MIT), sin
pasar por Studio y sin IDs escritos a mano. Todo pasa por `scripts/images.py`, desde la raíz del repo:

```bash
I=.claude/skills/own-images/scripts/images.py
python $I check   --game <Juego>          # nombres, formatos y tamaños; no necesita nada instalado
python $I preview --game <Juego>          # copia procesada en .asphalt-debug/ (alpha bleed, SVG→PNG); no sube
python $I sync    --game <Juego>          # simulacro: cuántas subidas y cuánto cupo
python $I sync    --game <Juego> --yes    # sube (después de la aprobación de quota-guard)
```

`<Juego>` es el nombre de la carpeta dentro de `ROBLOX_GAMES_HOME`, o una ruta.

## Entrada y convenciones

- **Entrada:** `games/<Juego>/assets/images/`, con subcarpetas si quieres (`icons/`, `ui/`, `decals/`).
  Formatos: `.png`, `.jpg`, `.bmp`, `.tga` y `.svg`. Asphalt pasa los SVG a PNG, y un SVG con
  `currentColor` sale en blanco, para poder teñirlo en Roblox.
- **Nombres:** minúsculas, dígitos, `-` y `_`, también en las carpetas: el nombre es la clave del
  módulo Luau. Renombrar un archivo cambia su clave y obliga a subirlo de nuevo.
- **Tamaño:** como mucho 1024 px por lado (Roblox reduce lo que pase de ahí) y menos de 20 MB.
- **El audio no va aquí.** Lo lleva `own-audio`, por su cupo pequeño y su SoundBank por roles. Asphalt
  solo lee `assets/images/`, así que ningún archivo se sube por los dos caminos.

## Qué hace `sync`

1. Ejecuta `check` y se para si hay archivos marcados con `!!` (salvo `--ignore-check`).
2. Pone Asphalt en el `aftman.toml` del juego, lo marca como confiable en Rokit y ejecuta `rokit install`.
3. Regenera `asphalt.toml` con el creador sacado de `ROBLOX_GROUP_ID` o `ROBLOX_USER_ID`. El archivo se
   ignora en git porque lleva el ID; se añade solo a `.gitignore`.
4. Cuenta las subidas pendientes con `asphalt sync cloud --dry-run` (sin clave y sin subir nada) y llama a
   `quota.py estimate opencloud-assets --op image-upload`.
5. **Sin `--yes` se para ahí.** Di al usuario cuántas imágenes son y espera su aprobación (`quota-guard`).
6. Con `--yes` sube con `ROBLOX_API_KEY` (pasada a Asphalt por variable de entorno, nunca por argumento) y
   registra en el cupo **solo lo que de verdad subió**.

Requisitos: `ROBLOX_API_KEY` (Open Cloud con `asset:read` y `asset:write`, del mismo creador) y
`ROBLOX_USER_ID` o `ROBLOX_GROUP_ID`. Nunca pidas esos valores en el chat: si faltan, explica cómo ponerlos
con `setx` (Windows) o `export` (macOS/Linux).

## Salida

- `asphalt.lock.toml`: hashes e IDs. **Haz commit** en el repo del juego: es lo que evita resubidas.
- `src/shared/Assets/`: el módulo Luau que genera Asphalt (estilo `nested`, sin extensiones). Úsalo por
  clave, por ejemplo `Assets.icons.coin`; mira el archivo generado tras la primera subida para ver la forma
  exacta. **Haz commit** también.
- Si la subida falla a mitad, lo ya subido queda en el lockfile: vuelve a ejecutar `sync --yes`.

## Qué no hacer

- No escribas IDs de imagen a mano en el código: usa el módulo generado.
- No edites `asphalt.toml` ni el módulo generado: los reescribe la skill.
- No subas imágenes de terceros sin derechos (ver `docs/licenses.md`).
