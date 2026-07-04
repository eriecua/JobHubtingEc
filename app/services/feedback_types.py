"""Central catalogs for Phase 6 feedback learning."""

from __future__ import annotations


EVENT_CATEGORY_IMPLICIT = "Implicita"
EVENT_CATEGORY_EXPLICIT = "Explicita"
EVENT_CATEGORY_OUTCOME = "Resultado"
EVENT_CATEGORY_CORRECTION = "Correccion"
EVENT_CATEGORY_PREFERENCE = "Preferencia"

EVENT_SOURCE_USER = "Usuario"
EVENT_SOURCE_INTERFACE = "Interfaz"
EVENT_SOURCE_HISTORICAL_IMPORT = "Importacion historica"
EVENT_SOURCE_MIGRATION = "Migracion"
EVENT_SOURCE_SYSTEM = "Sistema"

LEARNING_STATUS_CREATED = "Creado"
LEARNING_STATUS_ANALYZING = "Analizando"
LEARNING_STATUS_COMPLETED = "Completado"
LEARNING_STATUS_COMPLETED_WITH_WARNINGS = "Completado con observaciones"
LEARNING_STATUS_FAILED = "Fallido"

PROPOSAL_STATUS_PENDING = "Pendiente"
PROPOSAL_STATUS_APPROVED = "Aprobada"
PROPOSAL_STATUS_REJECTED = "Rechazada"
PROPOSAL_STATUS_APPLIED = "Aplicada"
PROPOSAL_STATUS_REVERTED = "Revertida"
PROPOSAL_STATUS_POSTPONED = "Pospuesta"
PROPOSAL_STATUS_EXPIRED = "Expirada"

RISK_LOW = "Bajo"
RISK_MEDIUM = "Medio"
RISK_HIGH = "Alto"

RELEVANT_EVENT_TYPES = {
    "saved",
    "explored",
    "prepared_application",
    "applied",
    "employer_response",
    "interview",
    "second_interview",
    "technical_test",
    "offer",
    "accepted_offer",
}

NEGATIVE_EVENT_TYPES = {
    "discarded",
    "employer_rejection",
    "no_response",
    "user_withdrawal",
}

OUTCOME_EVENT_TYPES = {
    "Sin respuesta": "no_response",
    "Respuesta automatica": "employer_response",
    "Contacto de reclutador": "employer_response",
    "Rechazo": "employer_rejection",
    "Prueba tecnica": "technical_test",
    "Entrevista": "interview",
    "Segunda entrevista": "second_interview",
    "Entrevista final": "second_interview",
    "Oferta": "offer",
    "Oferta aceptada": "accepted_offer",
    "Oferta rechazada": "user_withdrawal",
    "Postulacion retirada": "user_withdrawal",
    "Proceso cancelado": "user_withdrawal",
}
