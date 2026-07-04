# Radar Laboral Adaptativo - Master Plan

## Estado Actual

- Fases 1 a 6.1 implementadas y verificadas.
- Fase 2.1 implementada para carga asistida de perfil desde CV local en TXT, PDF seleccionable y DOCX.
- Fase 7 implementada: captura manual y semiautomatica desde fuentes autorizadas.

## Alcance Fase 7

- Configuracion local de fuentes de captura.
- Captura manual por boton, sin programador periodico.
- Conectores permitidos: CSV existente, carpeta local, EML guardado, RSS/Atom, API JSON publica autorizada, captura rapida por enlace.
- Conector de correo autorizado queda estructural y desactivado si no hay credenciales.
- Staging humano reutilizando importaciones existentes.
- Registro de errores, origen, hashes e idempotencia.
- Seguridad Fase 7: URLs publicas HTTP(S), redirects validados, bloqueo de redes privadas/locales y rechazo recursivo de credenciales en configuracion.

## Fuera De Alcance

- Fase 8: ejecucion programada.
- Fase 9: automatizaciones avanzadas.
- Scraping de portales, LinkedIn, captchas, login automatizado, envio de CV, envio de correos o postulacion automatica.
- IA opaca, embeddings o navegacion por LLM.

## Criterio De Aprobacion

- Pruebas automatizadas completas pasan.
- Alembic queda en `head`.
- Streamlit inicia sin errores de importacion.
- Capturas nuevas crean registros en staging, no vacantes finales sin aprobacion humana.
- El archivo original externo se conserva solo como contenido bruto/metadata de captura, no como accion automatica externa.
- Carpeta local no reprocesa el mismo archivo por defecto; el reproceso debe ser una configuracion explicita.
