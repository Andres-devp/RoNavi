# Créditos y licencias de terceros

Este repositorio **no incluye** contenido de terceros. `skills.lock.json` fija cada fuente
a un commit, y `scripts/setup.*` la descarga desde su repositorio original. Las
obligaciones prácticas de cada licencia están en `docs/licenses.md`.

## Skills y plugins

### SyphoDev Roblox Skills
- Repositorio: https://github.com/SyphoDev-yt/roblox-ai-skills (commit `f530452ea9390ba285ab506e070062c2f83fd83d`)
- Autor: **SyphoDev** — canal de YouTube: **https://www.youtube.com/@SyphoDev**
- Qué se usa: las 11 skills y los 7 agentes, instalados a nivel usuario con su propio instalador.
- Licencia: propia (`LICENSE.txt`).
  - Gratis, incluso para juegos comerciales.
  - **Prohibido venderlas**, modificadas o no, o incluirlas en un paquete de pago.
  - Si las compartes gratis, **enlaza al canal de SyphoDev** como fuente.
  - Esta plantilla no las redistribuye: las descarga del repositorio original.

### EL4CTEO / roblox-skills
- Repositorio: https://github.com/EL4CTEO/roblox-skills (tag `v1.1.0` = commit `11571e0622bb96c0d469e5c688bed7017c6b5cda`)
- Qué se usa: 23 skills de conocimiento, como plugin de Claude Code (`roblox-skills@roblox-skills`).
- Licencia: MIT, Copyright (c) 2026 EL4CTEO.

### xtrair / figma-to-roblox-ui
- Repositorio: https://github.com/xtrair/figma-to-roblox-ui (commit `6d5f376a9114ad1efdb1d4488f7ffd4a0690278d`)
- Qué se usa: el `SKILL.md` de la raíz, copiado a `.claude/skills/figma-to-roblox-ui/` junto con su `LICENSE`.
- Licencia: MIT, Copyright (c) 2026 Xtrair.

### TabooHarmony / roblox-brain
- Repositorio: https://github.com/TabooHarmony/roblox-brain (commit `38826be57ee37bcf023e9c2b85681bea3909281c`)
- Qué se usa: `skills/design/roblox-game-design` y `skills/design/roblox-player-psychology`, con sus carpetas `references/` completas.
- Licencia: MIT, Copyright (c) 2026 TabooHarmony.

### Figma (plugin oficial)
- `figma@claude-plugins-official`, del marketplace oficial de Anthropic (fuente: https://github.com/figma/mcp-server-guide).
- Uso sujeto a los términos de Figma y a tu plan.

## Bibliotecas de RoNavi Studio

No se incluyen en el repositorio: `ronavi.cmd` / `ronavi.sh` las instalan con pip en `.venv/`
desde PyPI, en la versión fijada en `ronavi/requirements.txt`.

- **Textual** (Textualize) — https://github.com/Textualize/textual — MIT.
- **Rich** (Textualize, dependencia de Textual) — https://github.com/Textualize/rich — MIT.

La mascota Navi y el resto de RoNavi Studio son propios de esta plantilla (MIT, ver `LICENSE`).

## Servidores MCP

- **Roblox Studio MCP**: integrado en Roblox Studio (Roblox Corporation).
- **ahujasid/blender-mcp** (`mcp-for-blender`): https://github.com/ahujasid/blender-mcp — MIT. No es un producto de la Blender Foundation.
- **Chrrxs/robloxstudio-mcp** (`@chrrxs/robloxstudio-mcp` 3.4.2): https://github.com/Chrrxs/robloxstudio-mcp — MIT.

## Fuentes tipográficas

- **Fredoka**, incluida en `roblox-ui/references/fonts` de SyphoDev. Licencia: SIL Open Font License 1.1 (https://openfontlicense.org).

## Modelos de IA

| Modelo | Uso | Licencia | Territorio |
|---|---|---|---|
| Hi3DGen / Stable3DGen (Bytedance) y pesos `Stable-X/trellis-normal-v0-1` | Imagen → 3D | MIT | **Sin cláusula territorial** |
| StableNormal / `yoso-normal` | Mapas de normales | Apache-2.0 | Sin cláusula |
| FLUX.1 [schnell] (Black Forest Labs), en Cloudflare Workers AI | Conceptos e iconos | Apache-2.0 | Sin cláusula |
| Tencent Hunyuan (Hunyuan3D, HY-Motion…) | **No se usa** | Licencia comunitaria de Tencent | **Excluye la UE, el Reino Unido y Corea del Sur**, también para el output |

## Herramientas

Rojo, Rokit, Wally, Lune, Selene, StyLua, luau-lsp y Asphalt (https://github.com/jackTabsCode/asphalt,
MIT; lo usa `own-images`) son proyectos de código abierto de sus autores (MPL-2.0 o MIT según el proyecto). Blender es GPL. Cada uno se instala
desde su fuente oficial; ninguno se redistribuye aquí.
