---
status: diagnosed
trigger: "El notebook 04 (y antes el 02) fallan al correr; a media sesión el venv pierde TODOS los paquetes (ModuleNotFoundError de cdd_mundial, jupyter_core, etc.) aunque minutos antes corrían 329 tests"
created: 2026-06-14
updated: 2026-06-14
---

# Debug: el venv dentro de OneDrive se deshidrata/corrompe intermitentemente

## Resumen ejecutivo
El entorno virtual `.venv/` vive dentro de una carpeta sincronizada por **OneDrive**
con **"Archivos a petición" (Files On-Demand)**. OneDrive convierte archivos del venv
en *placeholders* cloud-only (reparse points) y los deshidrata sin aviso. Cuando Python
arranca y `pyvenv.cfg` / `site-packages` están deshidratados o bloqueados, la
inicialización de `site` **no agrega `.venv\Lib\site-packages` a `sys.path`** y
**desaparecen todos los paquetes instalados** (incluido el editable `cdd_mundial` y
`jupyter`/`jupyter_core`). Es intermitente: funciona cuando los archivos están
hidratados, falla cuando OneDrive los volvió cloud-only.

Hay además un problema secundario, menor, en el notebook (abajo, "Capa 2").

## Síntomas
- **Capa 1 (entorno, raíz):** `.\.venv\python.exe -c "import cdd_mundial"` →
  `ModuleNotFoundError: No module named 'cdd_mundial'`. También falla
  `import jupyter_core`, y `python -m jupyter` → `No module named jupyter`.
  Aparece a media sesión, **después** de que el mismo venv corriera la suite completa
  (329 passed), nbconvert, e imports sin problema. No hubo desinstalación.
- **Capa 2 (notebook, menor):** al correr `notebooks/04_primer_pronostico_pipeline.ipynb`
  en VS Code/Antigravity, la **celda 1 imprime "Interfaz lista"** pero la **celda 2**
  (`verify_official(...)`) lanza
  `FileNotFoundError: [Errno 2] ... 'data\\external\\fixture_2026.csv'`.

## Root Cause
### Capa 1 — OneDrive deshidrata el venv (causa principal, recurrente)
- `Get-Item .venv\pyvenv.cfg).Attributes` → **`Archive, ReparsePoint`**.
  El `ReparsePoint` es el marcador de placeholder cloud-only de OneDrive Files
  On-Demand. Un archivo crítico del venv (pyvenv.cfg) es cloud-only.
- Con el venv en ese estado, `sys.path` quedó así (FALTA site-packages):
  ```
  ...\.venv\python312.zip
  ...\.venv\DLLs
  ...\.venv\Lib              <-- está Lib, pero NO Lib\site-packages
  ...\.venv
  ...\CDD-MUNDIAL
  ```
  Sin `...\.venv\Lib\site-packages` en `sys.path`, ningún paquete instalado importa.
- `site-packages` SÍ existe en disco (258 subcarpetas) y el editable está presente
  (`__editable__.cdd_mundial-0.1.0.pth`, `cdd_mundial-0.1.0.dist-info`). El problema
  no es que falten archivos, es que `site` no los engancha cuando están deshidratados/lockeados.
- Agravante: `pyvenv.cfg` tiene `home = ...\CDD-MUNDIAL\.venv` (auto-referencial) y el
  intérprete vive en `.venv\python.exe` (no en `.venv\Scripts\`), layout estilo `uv`
  más sensible a la deshidratación. Funciona cuando todo está hidratado; es frágil.

### Capa 2 — buffer del notebook viejo en el editor (menor, ya casi resuelto)
- El `FileNotFoundError` de la celda 2 ocurre porque el kernel arranca con CWD en
  `notebooks/` y la celda 2 usa rutas relativas. El notebook **en disco YA tiene** el
  guard que hace `os.chdir` a la raíz del repo (commit `74f08de`), pero VS Code corría
  una versión **vieja en caché** (celda 1 sin el `os.chdir`), por eso imprimía
  "Interfaz lista" sin haber cambiado de directorio.

## Evidencia / comandos para reproducir
```powershell
$py = ".\.venv\python.exe"
& $py -c "import sys; [print(p) for p in sys.path]"   # falta ...\.venv\Lib\site-packages
& $py -c "import cdd_mundial"                          # ModuleNotFoundError (intermitente)
(Get-Item ".venv\pyvenv.cfg").Attributes              # Archive, ReparsePoint  <-- cloud-only
Get-Content ".venv\pyvenv.cfg"                         # home auto-referencial, version 3.12.13
```

## Fix recomendado (durable) — recrear el venv FUERA de OneDrive
Saca el entorno de la carpeta sincronizada para que OneDrive no lo toque nunca.
Necesitas un Python 3.12 base REAL (no el stub de Microsoft Store; ver nota abajo).

```powershell
# 1. Crear venv fuera de OneDrive
py -3.12 -m venv C:\venvs\cdd-mundial          # o la ruta al python 3.12 base que uses
# 2. Activar e instalar el proyecto + stack (editable)
C:\venvs\cdd-mundial\Scripts\Activate.ps1
cd "C:\Users\jesus\OneDrive - ...\Documents\CDD-MUNDIAL"
python -m pip install -U pip
python -m pip install -e .                      # instala cdd_mundial editable + deps del pyproject
python -m pip install jupyterlab ipykernel nbconvert   # si no vienen como deps
# 3. Registrar el kernel python3 apuntando a ese venv (nombre python3 para pasar los tests)
python -m ipykernel install --user --name python3 --display-name "Python 3 (ipykernel)"
# 4. Verificar
python -c "import cdd_mundial; print(cdd_mundial.__file__)"   # debe resolver a ...\src\cdd_mundial
python -m pytest -q                                            # esperado: 329 passed
```
Nota Python base: en esta máquina `python` a secas resuelve al stub de Microsoft Store
(`...\WindowsApps\python.exe`), que NO sirve. Usa el launcher `py -3.12` o la ruta
absoluta a un Python 3.12 instalado (python.org / pyenv-win). Verifica con
`py -3.12 -c "import sys; print(sys.executable)"`.

## Fix rápido (stopgap, si no quieres recrear ahora)
- En el Explorador de Windows: clic derecho en la carpeta `.venv` →
  **"Conservar siempre en este dispositivo"** (fuerza a OneDrive a hidratar y no
  deshidratar). Reinicia el kernel después. El problema puede volver mientras el venv
  siga dentro de OneDrive.
- Opcional pero recomendado: excluir `.venv` de la sincronización de OneDrive.

## Fix del notebook (Capa 2) — ya basta con recargar
El notebook en disco está correcto. En VS Code/Antigravity:
1. Cerrar y reabrir el notebook (o paleta → "Revert File") para cargar la versión de disco.
2. **Restart Kernel**.
3. **Run All** (para que la celda 1 con el `os.chdir` corra primero).
4. Verificación rápida en una celda: `import sys; print(sys.executable)` debe terminar
   en el python del venv que estés usando.
- Idea opcional de robustez: cambiar el guard de la celda 1 por una búsqueda hacia
  arriba de `pyproject.toml` (subir hasta 8 niveles) en vez del `chdir` de un solo
  nivel — así resuelve la raíz desde cualquier CWD del editor. (No aplicado: no pude
  re-ejecutar el notebook con el venv caído.)

## Cómo verificar que quedó resuelto
1. `python -c "import cdd_mundial, jupyter_core; print('ok')"` con el intérprete elegido.
2. `python -m pytest -q` → 329 passed.
3. En el notebook (kernel = python3 del venv nuevo): **Run All** sin errores; la celda 2
   imprime el preview de `verify_official` con `order`, `model_version`, etc.

## Relacionado
- `.planning/debug/notebook-02-import-kernel.md` — el mismo origen (venv en OneDrive +
  kernel mal apuntado) golpeó al notebook 02 antes; se parchó el kernel `python3` para
  apuntar al venv, pero ese arreglo vive en `.venv` (gitignored) y es igual de frágil
  ante la deshidratación. La solución durable de AMBOS es sacar el venv de OneDrive.

## Estado del repo
La Fase 4 (código, tests, primera publicación oficial) está intacta y correcta — este
bug es 100% del entorno local (OneDrive + venv), no del código versionado. Con el venv
sano, `python -m pytest -q` da 329 passed.
