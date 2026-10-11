# Cupos gratis y cómo no bloquearse

Este archivo es la **única fuente de verdad** de los límites. La skill `quota-guard`
y su script `quota.py` leen las dos tablas marcadas como "máquina" directamente de aquí:
si una cifra cambia, se cambia **solo** en este archivo.

Reglas para editar las tablas máquina:

- La primera columna es una clave entre comillas invertidas (`` `clave` ``) y no se renombra.
- `límite` es un número, o `-` si no hay cifra publicada (entonces solo se registra el uso).
- `ventana` es una de: `daily-utc` (se reinicia a las 00:00 UTC), `rolling-<N><s|m|h|d>`
  (ventana móvil, por ejemplo `rolling-24h`, `rolling-7d`), o `none`.
- Cada fila lleva la fecha en que se verificó. Vuelve a verificar las de más de 90 días.

## Límites (tabla máquina)

| clave | servicio | límite | unidad | ventana | fuente | verificado |
|---|---|---|---|---|---|---|
| `cloudflare-workers-ai` | Cloudflare Workers AI (Flux schnell) | 10000 | neurons | daily-utc | [precios de Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) | 2026-10-11 |
| `kaggle-gpu` | GPU de Kaggle (Hi3DGen, Flux de respaldo) | 108000 | gpu-seconds | rolling-7d | Cuota visible en tu cuenta de Kaggle; ~30 h/semana según informes, Kaggle no publica cifra fija | 2026-10-11 |
| `hf-zerogpu` | Hugging Face ZeroGPU (cuenta gratis) | 300 | gpu-seconds | rolling-24h | [ZeroGPU: Usage Tiers](https://huggingface.co/docs/hub/spaces-zerogpu) | 2026-10-11 |
| `figma-mcp` | MCP de Figma (Education / Dev o Full) | 200 | calls | rolling-24h | [Figma MCP rate limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/) | 2026-10-11 |
| `figma-mcp-minute` | MCP de Figma, límite por minuto | 10 | calls | rolling-60s | [Figma MCP rate limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/) | 2026-10-11 |
| `figma-mcp-viewcollab` | MCP de Figma con asiento View/Collab | 20 | calls | rolling-30d | [Figma MCP rate limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/) | 2026-10-11 |
| `studio-procedural` | Studio `generate_procedural_model` | 50 | models | rolling-24h | [Assistant guide](https://create.roblox.com/docs/en-us/assistant/guide) | 2026-10-11 |
| `studio-generate-mesh` | Studio `generate_mesh` / `generate_material` | - | calls | none | Límite por minuto no publicado | 2026-10-11 |
| `opencloud-audio` | Open Cloud: subida de audio (con ID verificado) | 100 | uploads | rolling-30d | [Usage: Assets](https://create.roblox.com/docs/cloud/guides/usage-assets) (cifra conservadora, ver nota) | 2026-10-11 |
| `opencloud-assets` | Open Cloud: imágenes, mallas y modelos | - | uploads | none | Sin cupo mensual publicado | 2026-10-11 |
| `pollinations` | Pollinations (respaldo de imágenes) | - | images | none | Sin cupo publicado; usar con moderación | 2026-10-11 |
| `claude-pro` | Claude Pro (chat + Claude Code) | - | messages | none | claude.ai → Ajustes → Uso; límites compartidos entre chat y Claude Code que se reinician cada pocas horas | 2026-10-11 |
| `gemini-cli` | Gemini CLI / Antigravity CLI (respaldo) | - | requests | none | [Gemini CLI quotas](https://geminicli.com/docs/resources/quota-and-pricing/) — reemplazado por Antigravity CLI el 2026-06-18, cifra no verificada | 2026-10-11 |

## Costes por operación (tabla máquina)

| operación | clave | coste | fuente | verificado |
|---|---|---|---|---|
| `flux-1024-4steps` | cloudflare-workers-ai | 141 | Medido por SyphoDev (`roblox-ui/SKILL.md`); la tabla de precios da ~58 | 2026-10-11 |
| `flux-512-4steps` | cloudflare-workers-ai | 43 | 4,80 por tile de 512 + 9,60 por paso (tabla de precios) | 2026-10-11 |
| `hi3dgen-model` | kaggle-gpu | 102 | Medido por SyphoDev (`roblox-3d-model/SKILL.md`), sin contar el arranque del kernel | 2026-10-11 |
| `kaggle-kernel-boot` | kaggle-gpu | 300 | Estimación: instalación de dependencias y descarga de pesos | 2026-10-11 |
| `hf-space-generation` | hf-zerogpu | 60 | Duración por defecto de `@spaces.GPU` | 2026-10-11 |
| `figma-call` | figma-mcp | 1 | Una llamada de herramienta | 2026-10-11 |
| `procedural-model` | studio-procedural | 1 | Un modelo | 2026-10-11 |
| `audio-upload` | opencloud-audio | 1 | Una subida | 2026-10-11 |

## Resumen humano

| Servicio | Cupo gratis | Reinicio | Qué hacer al agotarse |
|---|---|---|---|
| Cloudflare Workers AI | 10.000 neurons al día (~70 imágenes de 1024 px con 4 pasos) | 00:00 UTC | Kaggle (`kaggle_run.py --mode images`) → Pollinations |
| Kaggle GPU | ~30 h/semana (mira tu cuenta), sesiones de hasta 12 h, ~100 s por modelo | Semanal (ventana móvil de 7 días como aproximación) | Space de Hugging Face → `generate_mesh` de Studio |
| HF ZeroGPU | 5 min/día con cuenta gratis (2 min sin sesión) | 24 h después del primer uso | Esperar o `generate_mesh` de Studio |
| Figma MCP | Education: 200/día y 10/min. View/Collab: 20/mes | Diario | Trabajar con capturas exportadas a mano |
| Studio procedurales | 50 en 24 h móviles | Ventana móvil | Esperar; usar piezas propias |
| Studio `generate_mesh` | Límite por minuto no publicado | — | Esperar un minuto y reintentar |
| Open Cloud audio | Ver nota: 100/mes (guía de Open Cloud) o 2.000 cada 30 días (página de audio) | 30 días | Esperar; usar sonidos de la Creator Store con `roblox-sfx` |
| Claude Pro | Compartido entre chat y Claude Code | Cada pocas horas | Esperar; Antigravity CLI como respaldo (no verificado) |

### Notas de verificación

- **Audio de Roblox: las dos páginas oficiales no coinciden** (verificado el 2026-10-11).
  - La [guía de uso de Open Cloud (Assets)](https://create.roblox.com/docs/cloud/guides/usage-assets) dice: hasta **100 subidas al mes** con ID verificado y **10** sin verificar.
  - La [página de audio](https://create.roblox.com/docs/en-us/audio/assets) dice **2.000 cada 30 días** verificados y **100** sin verificar.
  - `quota.py` usa la cifra conservadora (100). Si tu cuenta no está verificada, cambia el límite de `opencloud-audio` a 10.
- **Requisitos de audio de Roblox** (verificado el 2026-10-11, [página de audio](https://create.roblox.com/docs/en-us/audio/assets)):
  - `.mp3`, `.ogg`, `.wav` o `.flac`, de una sola pista.
  - Menos de 20 MB y menos de 7 minutos.
  - 48 kHz o menos, mono o estéreo.
  - Por Open Cloud: tipos `audio/mpeg`, `audio/ogg`, `audio/wav` y `audio/flac`. El audio no se puede actualizar: cada cambio es una subida nueva.
- **Cloudflare:** al pasar el cupo en el plan gratis, las llamadas fallan; no se cobra.
- **Figma:** si tienes Education pero el MCP sigue limitando como View/Collab, mira `docs/troubleshooting.md`.
- **Gemini CLI:** la página oficial dice que fue reemplazado por Antigravity CLI el 18 de junio de 2026 para el nivel gratuito. La cifra de 1.000 solicitudes al día ya no está garantizada.
