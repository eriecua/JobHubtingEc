---
name: radar-feature-builder
description: Implementa una función concreta del Radar Laboral de extremo a extremo, incluyendo dominio, persistencia, interfaz, pruebas y documentación. Úsala para añadir o modificar una característica específica.
---

# Radar Feature Builder

## Flujo
1. Localiza página, modelo, servicio, repositorio, tablas, configuración y pruebas afectadas.
2. Define estado actual, comportamiento deseado, reglas, errores, esquema, interfaz y criterios de aceptación.
3. Implementa por capas: modelo/DTO, validaciones, repositorio, servicio, migración, interfaz, pruebas y documentación.
4. No coloques reglas de negocio en Streamlit.
5. Usa transacciones coherentes, idempotencia y restricciones contra duplicados.

## Claves Streamlit
Usa claves estables por vista y entidad:
```python
form_key = f"decision_form_{view_key}_{priority.id}_{job.id}"
```
No uses el índice visual como única identidad.

## Pruebas mínimas
- Camino exitoso.
- Entrada inválida.
- Entidad inexistente.
- Duplicado o repetición.
- Persistencia.
- Compatibilidad con comportamiento anterior.
- Claves únicas cuando afecte Streamlit.

## Verificación
```powershell
python -m pytest <pruebas_focalizadas>
python -m pytest
python -m alembic current
```
Inicia Streamlit cuando cambie la interfaz.
