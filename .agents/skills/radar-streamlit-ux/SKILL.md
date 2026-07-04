---
name: radar-streamlit-ux
description: Diseña, simplifica o corrige la interfaz Streamlit del Radar Laboral. Úsala para navegación, formularios, tarjetas de vacantes, estados, claves duplicadas y flujos de usuario.
---

# Radar Streamlit UX

## Principios
- Una acción principal por pantalla.
- No mostrar IDs, hashes ni nombres técnicos al usuario.
- Diferenciar Abrir oferta original, Marcar como postulada, Guardar y Descartar.
- No afirmar que el sistema postuló cuando solo registró una decisión.
- Mostrar mensajes accionables, no trazas técnicas.

## Claves de widgets
Centraliza las claves:
```python
def widget_key(component: str, scope: str, *entity_ids: object) -> str:
    parts = [component, scope, *(str(value) for value in entity_ids)]
    return "_".join(part.strip().lower().replace(" ", "_") for part in parts)
```
Las claves deben ser únicas, estables, independientes del índice y legibles al depurar.

## Formularios
- No anides formularios.
- No renderices dos formularios para la misma entidad y alcance.
- Deduplica antes de renderizar.
- Evita efectos secundarios durante la construcción visual.

## Pruebas de interfaz
Lista vacía, una vacante, duplicados, vacante sin URL, URL inválida, dos pestañas, dos vistas con la misma vacante, rerun, error de base y texto largo.
