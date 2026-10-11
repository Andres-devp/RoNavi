---
name: quota-guard
description: Protege los cupos gratis de este estudio. Úsala ANTES de cualquier llamada que gaste un servicio gratis con límite - Cloudflare Workers AI (imágenes e iconos con Flux), GPU de Kaggle (Hi3DGen imagen→3D, Flux en Kaggle), el MCP de Figma, subidas de Open Cloud (sobre todo audio), generate_procedural_model / generate_mesh / generate_material de Studio y los Spaces de Hugging Face con ZeroGPU - y justo después para registrar lo gastado. Úsala también cuando pregunten cuánto cupo queda, por qué una generación falló con un error de límite o 429, o cuando haya que planear un lote de imágenes, iconos, mallas o subidas. Estima el costo, compara el registro con docs/quotas.md, pregunta antes de pasarse y elige el respaldo cuando un servicio se agota.
---

# quota-guard

Todos los servicios externos de este estudio son gratis con cupo. Quedarse sin cupo a
mitad de un lote desperdicia lo ya hecho, y algunos límites (procedurales de Studio,
audio de Open Cloud) tardan un día o un mes en volver. Esta skill hace que cada gasto
sea deliberado: **estimar → comprobar → preguntar si hace falta → llamar → registrar**.

Las cifras viven en `docs/quotas.md` y en ningún otro sitio. `scripts/quota.py` lee las
dos tablas "máquina" de ese archivo; si una cifra está mal, se corrige el documento, no
el script. El registro es `work/quota-ledger.json` (ignorado por git, propio de esta máquina).

```bash
Q=.claude/skills/quota-guard/scripts/quota.py     # desde la raíz del repo
python $Q status                                   # cada servicio: usado / límite / queda / reinicio
python $Q ops                                      # costos por operación conocidos
python $Q estimate cloudflare-workers-ai --op flux-1024-4steps --count 12
python $Q log      cloudflare-workers-ai --op flux-1024-4steps --count 12 --note "iconos tienda"
python $Q estimate opencloud-audio 5               # cantidad directa en la unidad del servicio
```

`estimate` sale con **0** si cabe, **2** si se pasaría del límite y **1** si hay error.

## Procedimiento

1. **Nombra el servicio y la operación.** Relaciona la llamada con una clave de
   `docs/quotas.md` (tabla de abajo) y cuenta las unidades del lote: una hoja de 12
   iconos son 12 × `flux-1024-4steps`; 4 modelos con Hi3DGen son
   `kaggle-kernel-boot` + 4 × `hi3dgen-model`.
2. **Estima.** Ejecuta `quota.py estimate` y dile al usuario el costo y lo que queda en
   una línea, por ejemplo: "12 iconos ≈ 1.692 neurons; quedan 8.308 hoy (reinicio 00:00 UTC)".
3. **Si sale con 2, para y pregunta.** Ofrece un lote más pequeño que quepa, esperar al
   reinicio que imprimió `quota.py`, o pasar al respaldo. Nunca te pases del cupo en
   silencio: en Cloudflare las llamadas simplemente fallan; en Studio y Open Cloud el
   cupo se pierde por un día o un mes.
4. **Haz la llamada.**
5. **Registra lo que de verdad se gastó** con `quota.py log` justo después, incluidos
   los intentos fallidos que también consumen (un kernel de Kaggle que arranca y luego
   falla ya gastó GPU). Si el costo real se aleja mucho de la tabla, dilo: hay que
   actualizar los costos de `docs/quotas.md`.

Lotes con subagentes: el hilo principal estima y registra todo el lote. Los
subagentes no llaman a `quota.py log`, así un lote paralelo no cuenta dos veces.

## Claves de servicio

| Llamada prevista | Clave | Operación típica |
|---|---|---|
| Flux schnell en Cloudflare (`gen_icons_cf.py`, `gen_concepts_cf.py`) | `cloudflare-workers-ai` | `flux-1024-4steps` |
| Kernel de Kaggle (`kaggle_run.py push`, cualquier modo) | `kaggle-gpu` | `kaggle-kernel-boot` + `hi3dgen-model` |
| Space de Hugging Face (`image_to_3d.py`, `concept_image.py` con un Space) | `hf-zerogpu` | `hf-space-generation` |
| Cualquier herramienta del MCP de Figma salvo `whoami` | `figma-mcp` (+ `figma-mcp-minute`) | `figma-call` |
| `generate_procedural_model` de Studio | `studio-procedural` | `procedural-model` |
| `generate_mesh` / `generate_material` de Studio | `studio-generate-mesh` | solo registro, sin límite publicado |
| Subida de audio por Open Cloud (`own-audio`) | `opencloud-audio` | `audio-upload` |
| Subida de imagen o malla por Open Cloud | `opencloud-assets` | solo registro |

Reglas de reinicio, tal como están en `docs/quotas.md`: Cloudflare diario a las 00:00
UTC; Kaggle semanal (se lleva como ventana móvil de 7 días porque Kaggle solo muestra
el reinicio real en la cuenta); Figma diario; procedurales de Studio en ventana móvil
de 24 h; ZeroGPU 24 h después del primer uso; audio de Open Cloud cada 30 días.

Si el asiento de Figma es View/Collab, usa `figma-mcp-viewcollab` (20 al mes) en vez de
`figma-mcp` y avisa pronto de que Figma se agotará rápido.

## Respaldos, en orden

Cuando un servicio se agota (o se agotaría), ofrece el siguiente. Cada respaldo tiene
su propio cupo, así que estímalo también.

**Imágenes e iconos**
1. Cloudflare Workers AI (Flux schnell): `gen_icons_cf.py` / `gen_concepts_cf.py`.
2. Kaggle: `python ~/.claude/skills/roblox-3d-model/scripts/kaggle_run.py push --mode images ...`
   (gasta GPU de Kaggle).
3. Pollinations: el backend sin clave de `concept_image.py`. Más lento, menos calidad, ~1 solicitud cada 15 s.

**3D (imagen → malla)**
1. Hi3DGen en Kaggle: `kaggle_run.py push --mode meshes` (~102 s de GPU por modelo).
2. Space de Hugging Face: `image_to_3d.py` (300 s de GPU al día con cuenta gratis: 1–3 modelos).
3. `generate_mesh` de Studio por MCP (sin cupo publicado, limitado por minuto; menos control de la topología).

**Audio**: cupo de Open Cloud agotado → usa sonidos de la Creator Store por ID con
`roblox-sfx` (sin subida, sin cupo) hasta que se libere la ventana.

**Claude**: si los límites de Claude Pro están cerca, termina la sección actual, escribe
`HANDOFF.md` y para limpiamente en vez de dejar trabajo a medias.

## Informe

Cuando pregunten "¿cuánto cupo me queda?", ejecuta `quota.py status` y resume en
español solo los servicios con uso o con menos del 10 % libre, con su próximo reinicio.
