---
name: radar-release-check
description: Verifica que una versión del Radar Laboral esté lista para uso local. Úsala antes de una entrega, al cerrar una fase o cuando se pregunte si el proyecto ya funciona.
---

# Radar Release Check

## Checklist
- Entorno virtual, Python, dependencias y configuración.
- Sin secretos versionados.
- Respaldo local.
- `alembic current`, `alembic heads` y `upgrade head`.
- Base nueva temporal y actualización desde una revisión anterior cuando aplique.
- `python -m pytest` con total, aprobadas, fallidas y duración.
- Inicio de Streamlit.
- Flujos: Inicio, Ofertas, Importación, Detalle, Enlace original, Decisión, Postulación, Seguimiento, Perfil y Configuración avanzada.
- Rerun sin claves duplicadas.
- Sin pérdida de datos ni duplicados nuevos.
- README y comandos Windows actualizados.

## Veredicto
Aprobada, Aprobada con observaciones o No aprobada. Incluye evidencia y bloqueadores.
