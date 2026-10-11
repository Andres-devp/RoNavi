# Pipeline: de la idea al juego publicado

`create-roblox-game` (SyphoDev) es la puerta de entrada. Lleva un juego por 6 secciones,
**una por sesión**, con `HANDOFF.md` entre secciones y la palabra "approved" para cerrar cada una.

```mermaid
flowchart LR
    S1["1 · Investigación y plan"] --> S2["2 · Código"]
    S2 --> S3["3 · Arte"]
    S3 --> S4["4 · Animación y sonido"]
    S4 --> S5["5 · Playtest"]
    S5 --> S6["6 · Publicar"]
    S1 -. HANDOFF.md + approved .-> S2
```

| Fase | Skill principal | Apoyo |
|---|---|---|
| Investigación y plan | `create-roblox-game` (sección 1) | `roblox-game-design`, `roblox-player-psychology`, agente `roblox-market-scout` |
| Código | `roblox-code` (4 revisiones: `rojo build`, `lune run test`, `selene`, `stylua`) | `roblox-skills:roblox-luau`, `roblox-networking`, `roblox-security`, `roblox-data-stores` |
| Mapa | `roblox-map` (spec → greybox → prover) | `roblox-skills:roblox-world-building` |
| Modelos 3D | `roblox-3d-model` | `roblox-texture-gen`, `quota-guard` |
| UI | `roblox-ui` (desde spec) · `figma-to-roblox-ui` (desde Figma) | MCP `figma`, `quota-guard` |
| VFX | `roblox-vfx` (librería de packs propios) | `docs/licenses.md` |
| Animación | `roblox-animation` (Blender sin ventana) | — |
| Sonido | `roblox-sfx` (Creator Store) · `own-audio` (propio) | `quota-guard` |
| Ensamblar en Studio | `create-roblox-game` + MCP `Roblox_Studio` | `roblox-skills:roblox-studio-mcp` |
| Playtest y publicar | `create-roblox-game` (secciones 5 y 6) | `studio-doctor` si algo falla |

`roblox-build-orchestrator` puede lanzar en paralelo las fases de assets con los 7 agentes. Los agentes trabajan en disco y nunca tocan Studio; el hilo principal ensambla.

## 3D: imagen → modelo en Studio

```mermaid
flowchart LR
    A["Concepto<br/>(Flux en Cloudflare)"] --> B["Hi3DGen en Kaggle<br/>~102 s de GPU"]
    B --> C["Blender sin ventana<br/>weld · decimate (tope 20.000 tris, objetivo menos de 10.000) · UV · bake"]
    C --> D{"¿Permanente?"}
    D -- sí --> E["Open Cloud<br/>upload_asset.py (Model / Image)"]
    D -- prototipo --> F["EditableMesh<br/>(serve_assets.py)"]
    E --> G["Studio por MCP"]
    F --> G
    Q["quota-guard"] -. antes de Flux y Kaggle .-> A
```

- Respaldos de la malla: Space de Hugging Face (`image_to_3d.py`) → `generate_mesh` de Studio.
- Para una textura se sube un `Image`, no un `Decal`: un Decal tiene otro ID y el modelo queda gris. Lo explica `upload_asset.py`.
- Hunyuan3D no se usa: su licencia excluye la UE, el Reino Unido y Corea del Sur (ver `docs/licenses.md`).

## Iconos: Flux → recorte → subida

```mermaid
flowchart LR
    A["Manifest de iconos"] --> Q["quota-guard<br/>estimate"]
    Q --> B["gen_icons_cf.py<br/>Flux schnell en Cloudflare"]
    B --> C["icon_cutout.py<br/>recorte y fondo transparente"]
    C --> D["upload_icons.py<br/>Open Cloud (Image)"]
    D --> E["gen_icon_bank.py<br/>IconBank en el código"]
```

## UI desde spec

```mermaid
flowchart LR
    A["spec JSON<br/>(examples/coin_hud.json)"] --> B["ui_build.py"]
    B --> C["mockup PNG"]
    B --> D[".model.json<br/>(Rojo)"]
    B --> E["builder Luau"]
    D --> F["verify_ui.py<br/>layout · texto · táctil"]
    F --> G["rojo serve → Studio"]
```

## UI desde Figma

```mermaid
flowchart LR
    A["Frame en Figma"] --> B["MCP figma<br/>get_metadata · get_design_context · get_screenshot"]
    B --> C["figma-to-roblox-ui<br/>Scale, AnchorPoint 0.5, UIStroke escalado"]
    C --> D["MCP Roblox_Studio<br/>execute_luau (pregunta)"]
    D --> E["screen_capture<br/>comparar con el frame"]
    Q["quota-guard<br/>figma-mcp: 200/día, 10/min"] -. cada llamada .-> B
```

Al terminar, pasa la UI a disco: el disco es la verdad, así que lo que se construyó en Studio por MCP se exporta a `.model.json` o a un builder Luau dentro del proyecto Rojo.

## Sonido

```mermaid
flowchart LR
    subgraph Store["Creator Store"]
      A["roblox-sfx<br/>find → pick → manifest.json"]
    end
    subgraph Own["Propio (DAW)"]
      B["source/*.wav"] --> C["own-audio build<br/>ffmpeg: LUFS/pico · mono/estéreo · OGG"]
      C --> D["own-audio upload<br/>quota-guard · caché por hash"]
    end
    A --> E["SoundBank.luau + Sfx.luau"]
    D --> E
```
