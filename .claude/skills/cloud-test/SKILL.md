---
name: cloud-test
description: Ejecuta las specs de un juego DENTRO de un servidor real de Roblox, sin abrir Studio, con Open Cloud Luau Execution - construye el place con Rojo, guarda una versión en un place de PRUEBAS, corre tests/**/*.spec.luau con el motor de verdad (Vector3, CFrame, Instance, task…) y muestra PASS/FAIL. Úsala cuando una spec necesite APIs del motor que Lune no tiene, antes de publicar una versión, cuando el usuario pida "probar en Roblox", "tests en la nube" o "CI", o para confirmar que `lune run test` y el motor dan lo mismo. NO sustituye a check.py (que va primero y es gratis) ni al playtest en Studio.
---

# cloud-test

`lune run test` prueba la lógica pura sin motor. Esta skill corre **las mismas specs** (y las que
necesitan el motor) en un servidor de Roblox por [Open Cloud Luau Execution](https://create.roblox.com/docs/cloud/reference/features/luau-execution).

```bash
C=.claude/skills/cloud-test/scripts/cloud_test.py
python $C --game <Juego>          # simulacro: construye el place de pruebas, enseña el plan y el cupo
python $C --game <Juego> --yes    # guarda una versión en el place de PRUEBAS y corre las specs
```

## Antes de la primera vez (lo hace el usuario)

1. **Un place solo para pruebas.** Crea una experiencia nueva en el Creator Dashboard (o un place
   aparte dentro de la tuya). **Nunca el juego publicado:** `--yes` guarda una versión nueva (tipo
   *Saved*, no *Published*), y esa versión pasa a ser la que abre el place.
2. Sus IDs como variables de entorno: `ROBLOX_TEST_UNIVERSE_ID` y `ROBLOX_TEST_PLACE_ID`, o `--universe` y `--place`.
3. `ROBLOX_API_KEY` con acceso a esa experiencia y los permisos **universe-places: Write** y
   **universe.place.luau-execution-session: Write**.
4. Nunca pidas esos valores en el chat: explica cómo ponerlos con `setx` (Windows) o `export` (macOS/Linux).

## Procedimiento

1. **`check.py` primero.** Si las cuatro revisiones no están en verde, no gastes una tarea en la nube.
2. **Simulacro** (sin `--yes`): construye el place, cuenta las specs y llama a `quota.py estimate` para
   `opencloud-place-publish` y `opencloud-luau-exec` (5 tareas por minuto). Si sale con 2, espera un minuto.
3. **`--yes`.** Di antes qué place se va a tocar (el script lo imprime). Después el script:
   - construye el juego más `ServerStorage.RoNaviCloudTests`, con `tests/` y `src/shared/` como en el disco,
     para que `require("../src/shared/...")` funcione igual que en Lune;
   - guarda la versión, crea la tarea con `scripts/runner.luau` y la espera (5 minutos como mucho);
   - imprime los logs de la tarea, PASS/FAIL por test y sale con 1 si algo falló;
   - registra en `quota-guard` la versión y la tarea, también si después fallan.
4. **Informa** igual que con `check.py`: cuántos pasaron, qué falló y el mensaje de error.

## Specs

- Mismo contrato que el scaffold: un `tests/X.spec.luau` devuelve `{ [nombre]: () -> () }` y un test pasa si no lanza error.
- **Specs que necesitan el motor:** ponlas en `tests/engine/`. Lune solo lee `tests/` sin subcarpetas, así
  que no las ejecuta en local, y esta skill las ejecuta en Roblox. Desde ahí, el código del juego se requiere
  con `require("../../src/shared/...")`.
- Los scripts del place (servidor y cliente) **no** se ejecutan durante la tarea, y la física tampoco.
  Prueba módulos, no el arranque del juego: eso sigue siendo cosa del playtest en Studio.

## Límites

- 5 creaciones de tarea por minuto por dueño de la clave, como mucho 10 tareas sin terminar por place,
  5 minutos por tarea y 450 KB de logs (ver `docs/quotas.md`).
- Si el place de pruebas pertenece a un grupo, la clave tiene que tener acceso a esa experiencia.
