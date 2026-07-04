---
name: radar-safe-migrations
description: Crea, revisa, prueba o corrige migraciones Alembic seguras para el Radar Laboral. Úsala cuando cambien modelos, columnas, índices, relaciones o restricciones.
---

# Radar Safe Migrations

## Antes de cambiar
```powershell
python -m alembic current
python -m alembic heads
python -m alembic history
```
Inspecciona `alembic.ini`, `alembic/env.py`, revisiones recientes y modelos afectados.

## Reglas
- Una revisión por cambio lógico.
- Revisa manualmente el autogenerado.
- No confíes ciegamente en `--autogenerate`.
- Para columnas no nulas en tablas con datos, usa una transición segura.
- Detecta duplicados antes de agregar una restricción única.
- No borres tablas o columnas sin autorización.
- Prefiere una migración correctiva a editar una revisión ya aplicada.
- No mezcles fases distintas en una revisión.

## Pruebas
1. Base temporal desde cero.
2. `upgrade head`.
3. Verificar tablas y restricciones.
4. Insertar datos representativos.
5. Probar downgrade cuando sea seguro.
6. Volver a `upgrade head`.
7. Ejecutar todas las pruebas.
