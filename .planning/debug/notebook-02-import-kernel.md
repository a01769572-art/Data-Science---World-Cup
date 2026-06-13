---
status: resolved
trigger: "notebook 02 modelos baseline falla al compilar la celda bajo el heading '2. Configuración reproducible'; el resto de celdas python fallan porque no se importan las librerías/módulos desde src"
created: 2026-06-12
updated: 2026-06-12
---

# Debug: notebook 02 — fallo de imports desde src (cdd_mundial)

## Síntomas
- La primera celda de código (bajo "2. Configuración reproducible") falla.
- El fallo es de importación: `from cdd_mundial.models import predict_lambdas` (módulos desde `src/`).
- Todas las celdas posteriores fallan en cascada por depender de esos imports.
- El notebook tiene outputs guardados de una corrida exitosa previa → antes funcionaba.

## Root Cause
El notebook está enlazado al kernelspec llamado `python3`
(`.venv/share/jupyter/kernels/python3/kernel.json`), registrado con un `argv`
NO absoluto: `"python"`. En esta máquina, `python` a secas resuelve al stub de
Microsoft Store (`...\AppData\Local\Microsoft\WindowsApps\python.exe`), no al
venv del proyecto. Ese stub no tiene el stack científico ni el paquete editable
`cdd_mundial` (instalado vía `__editable__.cdd_mundial-0.1.0.pth` en `.venv`).
Por eso la celda de imports revienta y todo lo demás cae en cascada.

El kernel correcto ya existía: `cdd-mundial` → ruta absoluta `.venv\python.exe`,
donde `import cdd_mundial` resuelve a `src\cdd_mundial\__init__.py`.

## Evidencia
- `__editable__.cdd_mundial-0.1.0.pth` + `cdd_mundial-0.1.0.dist-info` presentes en `.venv\Lib\site-packages`.
- `& .venv\python.exe -c "import cdd_mundial"` → OK (resuelve a `src\cdd_mundial`).
- `Get-Command python` → `...\WindowsApps\python.exe` (stub MS Store).
- notebook `metadata.kernelspec.name = "python3"`; ese kernel.json usaba `argv[0]="python"`.

## Fix aplicado
Reparado `.venv/share/jupyter/kernels/python3/kernel.json`: `argv[0]` cambiado de
`"python"` a la ruta absoluta `...\CDD-MUNDIAL\.venv\python.exe`.

Verificación: ejecutar toda la cadena de imports de la celda fallida con ese
intérprete → `ALL IMPORTS OK`.

## Para que surta efecto
- En JupyterLab: **Kernel → Restart Kernel** (kernel.json se lee al arrancar el kernel).
- Alternativa equivalente: **Kernel → Change Kernel → "Python (CDD-MUNDIAL)"** (el kernelspec `cdd-mundial`, ya correcto).

## Files changed
- `.venv/share/jupyter/kernels/python3/kernel.json`
