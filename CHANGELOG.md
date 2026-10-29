# Cambios de RoNavi Studio

Cada versión es un tag `vX.Y.Z` con su GitHub Release (las notas salen de esta página).
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones,
[SemVer](https://semver.org/lang/es/). Cómo publicar una: `docs/ronavi.md` → *Versiones*.

## [0.2.0] - 2026-10-29

### Añadido

- **Explorar idea**: investiga un juego sin ponerle nombre, género ni descripción. Claude trabaja en
  `work/ideas/<fecha>/`, sin git, con su propio guardián, y escribe tres conceptos en `IDEA.md`.
  Desde *Nuevo juego → Ideas guardadas* la idea se convierte en juego y su investigación se copia a
  `docs/research/`. En la CLI: `ronavi idea`, `ronavi ideas` y `ronavi new … --from-idea <id>`.
- **Instalador de una línea**: `install.ps1` (Windows) e `install.sh` (macOS/Linux) clonan el estudio
  en la última versión, ponen `ronavi` en el PATH y lo abren. Volver a ejecutarlos actualiza.
- **Actualizar**: `ronavi update` y *Configuración → Actualizar RoNavi*. Una instalación pasa al tag
  más nuevo; un clon de desarrollo hace `git pull --ff-only`. Al arrancar, RoNavi avisa (una vez al día)
  si hay una versión nueva.
- `ronavi path [add]` y un paso del asistente para escribir `ronavi` en cualquier terminal.
- `ronavi --version` muestra también el tag o commit de git.
- Workflow `release` que publica la GitHub Release al subir un tag `vX.Y.Z`.

## [0.1.0] - 2026-10-11

### Añadido

- Primera versión de RoNavi Studio: interfaz de terminal, juegos aislados con su propio git y guardián,
  asistente de instalación, skills, herramientas e integraciones.
