# Licencias y obligaciones

Resumen práctico de lo que obliga cada pieza. Las licencias completas están en cada
repositorio (`vendor/<fuente>/LICENSE*` tras el setup) y los créditos en `THIRD_PARTY.md`.
Esto no es asesoría legal: ante la duda, lee la licencia original.

## Código y skills

| Pieza | Licencia | Qué te obliga |
|---|---|---|
| Esta plantilla (archivos propios) | MIT | Conservar el aviso de copyright si la redistribuyes |
| SyphoDev Roblox Skills | Licencia propia (`LICENSE.txt`) | Uso gratis, también en juegos comerciales. **Prohibido venderlas** o meterlas en un paquete de pago, también modificadas. Si las compartes gratis, **enlaza al canal de SyphoDev**: https://www.youtube.com/@SyphoDev |
| EL4CTEO/roblox-skills | MIT | Conservar el aviso de copyright y la licencia al redistribuir |
| xtrair/figma-to-roblox-ui | MIT | Ídem (el setup copia su `LICENSE` junto al `SKILL.md`) |
| TabooHarmony/roblox-brain | MIT | Ídem (el setup copia su `LICENSE` en cada skill) |
| Plugin oficial de Figma | Términos de Figma y del marketplace oficial | Uso de la API sujeto a tu plan de Figma |

Por eso este repositorio **no contiene** contenido de terceros. Solo guarda `skills.lock.json`, y el setup descarga cada pieza desde su repositorio original.

## Lo que llega al juego publicado

| Recurso | Licencia | Obligación en el juego |
|---|---|---|
| Fuente **Fredoka** (en `roblox-ui/references/fonts`) | SIL Open Font License 1.1 | Puedes usarla en el juego y en imágenes. No vendas la fuente sola. Si redistribuyes el archivo de la fuente, incluye la licencia OFL. |
| Mallas generadas con **Hi3DGen** (código MIT, Bytedance; pesos `trellis-normal` MIT) | MIT | Uso comercial permitido y **sin cláusula territorial**. Atribución recomendada en los créditos del juego. |
| Imágenes de **Flux schnell** (Cloudflare Workers AI) | Apache-2.0 (modelo) + términos de Cloudflare | Uso comercial permitido |
| **Packs de VFX de la Creator Store** (para `roblox-vfx`) | Términos de la Creator Store y de cada pack | Usarlos en **tu** juego está dentro de los términos. Extraer sus texturas y valores y **redistribuirlos** como pack propio no lo está. Revisa la descripción de cada pack: algunos piden crédito. |
| **Sonidos de la Creator Store** (`roblox-sfx`) | Términos de la Creator Store | Se usan por ID, sin resubirlos. Respeta la privacidad de audio del dueño. |
| **Audio propio** (`own-audio`) | Tuyo | Sube solo lo que es tuyo o tienes derecho a usar |
| Modelos **Hunyuan3D** (Tencent) | Licencia comunitaria de Tencent | **No se usan.** La licencia **no aplica en la UE, el Reino Unido ni Corea del Sur**, y la restricción alcanza también al *output*. |

### Atribución en el juego

Cuando un pack de VFX, un sonido o un modelo pida crédito, añádelo a un apartado
"Créditos" del juego: en la descripción de la experiencia o en una pantalla dentro del
juego. Lleva una lista por juego en `games/<Juego>/CREDITS.md` con el nombre del
recurso, el autor, el enlace y la licencia, y cópiala a la descripción al publicar.

### Antes de publicar

- [ ] Cada pack de VFX que usa el juego está en `CREDITS.md`, con sus condiciones revisadas.
- [ ] No hay modelos ni salidas de Hunyuan ni de otro modelo con cláusula territorial.
- [ ] El audio subido es propio o de la Creator Store usado por ID.
- [ ] La descripción del juego incluye los créditos que pidan los autores.
