"""SQLAlchemy database models for the first project phase."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import JSON as SQLAlchemyJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def utc_now() -> datetime:
    """Return the current UTC timestamp for database defaults."""

    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    """Shared created/updated timestamp fields."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Job(TimestampMixin, Base):
    """Stored job vacancy."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(120), default="Ecuador", nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    location_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    province: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    modality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    workplace_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    schedule_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_period: Mapped[str | None] = mapped_column(String(80), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    salary_is_estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_min_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    experience_max_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String(120), nullable=True)
    languages_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    travel_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    relocation_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(160), nullable=True)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category: Mapped[str | None] = mapped_column(String(160), nullable=True)
    vacancies_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="nueva", nullable=False, index=True)
    data_quality_status: Mapped[str] = mapped_column(String(80), default="Minima", nullable=False, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_of_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspicious_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(80), default="Pendiente", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    deduplication_key: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)

    interactions: Mapped[list[Interaction]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    recommendation_scores: Mapped[list[RecommendationScore]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    status_history: Mapped[list[JobStatusHistory]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="JobStatusHistory.job_id",
    )
    tag_assignments: Mapped[list[JobTagAssignment]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    job_requirements: Mapped[list[JobRequirement]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list[JobEvaluation]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    priorities: Mapped[list[JobPriority]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[list[JobDecision]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    effort_overrides: Mapped[list[ApplicationEffortOverride]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    feedback_events: Mapped[list[FeedbackEvent]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    duplicate_of: Mapped[Job | None] = relationship(remote_side=[id])


class Interaction(Base):
    """User interaction or decision recorded for a vacancy."""

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    job: Mapped[Job] = relationship(back_populates="interactions")


class Application(TimestampMixin, Base):
    """Application tracking record for a vacancy."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("professional_profiles.id"), nullable=True, index=True)
    application_date: Mapped[date] = mapped_column(Date, nullable=False)
    cv_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(120), default="iniciada", nullable=False, index=True)
    response_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    interview_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offer_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="applications")
    profile: Mapped[ProfessionalProfile | None] = relationship(back_populates="applications")
    outcomes: Mapped[list[ApplicationOutcome]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )


class RecommendationScore(Base):
    """Persisted recommendation score generated for a vacancy."""

    __tablename__ = "recommendation_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_details: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    job: Mapped[Job] = relationship(back_populates="recommendation_scores")


class JobRequirement(TimestampMixin, Base):
    """Structured requirement extracted or manually added for a job."""

    __tablename__ = "job_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    requirement_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    importance: Mapped[str] = mapped_column(String(80), default="No determinada", nullable=False, index=True)
    source_field: Mapped[str] = mapped_column(String(120), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), nullable=False)
    extraction_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.50"), nullable=False)
    skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    tool_id: Mapped[int | None] = mapped_column(ForeignKey("tools.id"), nullable=True)
    is_confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    job: Mapped[Job] = relationship(back_populates="job_requirements")
    skill: Mapped[Skill | None] = relationship()
    tool: Mapped[Tool | None] = relationship()


class EvaluationRun(Base):
    """Batch or individual compatibility evaluation run."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    profile_snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="Creado", nullable=False, index=True)
    jobs_requested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    evaluations: Mapped[list[JobEvaluation]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class JobEvaluation(TimestampMixin, Base):
    """Versioned compatibility evaluation for a job and profile."""

    __tablename__ = "job_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, index=True)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    data_coverage_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strengths: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    gaps: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    missing_information: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    hard_constraint_results: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    growth_opportunities: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    summary_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    profile_snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    run: Mapped[EvaluationRun] = relationship(back_populates="evaluations")
    job: Mapped[Job] = relationship(back_populates="evaluations")
    profile: Mapped[ProfessionalProfile] = relationship()
    components: Mapped[list[EvaluationComponent]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )


class EvaluationComponent(Base):
    """One scored compatibility dimension for an evaluation."""

    __tablename__ = "evaluation_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("job_evaluations.id"), nullable=False, index=True)
    component_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    awarded_points: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    missing_data: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    evaluation: Mapped[JobEvaluation] = relationship(back_populates="components")


class PrioritizationRun(Base):
    """Batch or individual strategic prioritization run."""

    __tablename__ = "prioritization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    prioritization_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evaluation_run_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="Creado", nullable=False, index=True)
    jobs_considered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_prioritized: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_excluded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    priorities: Mapped[list[JobPriority]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class JobPriority(TimestampMixin, Base):
    """Strategic priority assigned to an evaluated job."""

    __tablename__ = "job_priorities"
    __table_args__ = (
        UniqueConstraint("prioritization_run_id", "position_in_queue", name="uq_priority_run_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prioritization_run_id: Mapped[int] = mapped_column(ForeignKey("prioritization_runs.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    evaluation_id: Mapped[int | None] = mapped_column(ForeignKey("job_evaluations.id"), nullable=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    priority_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, index=True)
    urgency_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    strategic_value_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    actionability_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    application_effort_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    priority_bucket: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    position_in_queue: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    decision_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    blocking_factors: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evaluation_snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    run: Mapped[PrioritizationRun] = relationship(back_populates="priorities")
    job: Mapped[Job] = relationship(back_populates="priorities")
    evaluation: Mapped[JobEvaluation | None] = relationship()
    profile: Mapped[ProfessionalProfile] = relationship()


class JobDecision(TimestampMixin, Base):
    """Human decision taken for a job priority."""

    __tablename__ = "job_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    priority_id: Mapped[int | None] = mapped_column(ForeignKey("job_priorities.id"), nullable=True, index=True)
    decision: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reason_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    decision_source: Mapped[str] = mapped_column(String(80), default="Usuario", nullable=False, index=True)

    job: Mapped[Job] = relationship(back_populates="decisions")
    profile: Mapped[ProfessionalProfile] = relationship()
    priority: Mapped[JobPriority | None] = relationship()


class ApplicationEffortOverride(TimestampMixin, Base):
    """Manual application effort override for a job/profile pair."""

    __tablename__ = "application_effort_overrides"
    __table_args__ = (UniqueConstraint("job_id", "profile_id", name="uq_effort_override_job_profile"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    effort_level: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="effort_overrides")
    profile: Mapped[ProfessionalProfile] = relationship()


class FeedbackEvent(Base):
    """Deduplicated explicit, implicit, outcome or correction signal."""

    __tablename__ = "feedback_events"
    __table_args__ = (UniqueConstraint("deduplication_key", name="uq_feedback_event_deduplication_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    evaluation_id: Mapped[int | None] = mapped_column(ForeignKey("job_evaluations.id"), nullable=True, index=True)
    priority_id: Mapped[int | None] = mapped_column(ForeignKey("job_priorities.id"), nullable=True, index=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    signal_value: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="feedback_events")
    job: Mapped[Job] = relationship(back_populates="feedback_events")
    evaluation: Mapped[JobEvaluation | None] = relationship()
    priority: Mapped[JobPriority | None] = relationship()
    application: Mapped[Application | None] = relationship()


class ApplicationOutcome(TimestampMixin, Base):
    """Detailed outcome stage for an application."""

    __tablename__ = "application_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    outcome_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    outcome_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    company_response: Mapped[str] = mapped_column(String(120), nullable=False)
    user_assessment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    salary_offered: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(180), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped[Application] = relationship(back_populates="outcomes")


class LearningRun(Base):
    """One deterministic learning analysis execution."""

    __tablename__ = "learning_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    learning_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="Creado", nullable=False, index=True)
    feedback_events_considered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applications_considered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outcomes_considered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    proposals_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings_json: Mapped[list[str] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="learning_runs")
    metrics: Mapped[list[LearningMetric]] = relationship(
        back_populates="learning_run",
        cascade="all, delete-orphan",
    )
    proposals: Mapped[list[AdjustmentProposal]] = relationship(
        back_populates="learning_run",
        cascade="all, delete-orphan",
    )


class LearningMetric(Base):
    """Explainable learning metric produced by a learning run."""

    __tablename__ = "learning_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    learning_run_id: Mapped[int] = mapped_column(ForeignKey("learning_runs.id"), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    metric_scope: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    confidence_level: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    learning_run: Mapped[LearningRun] = relationship(back_populates="metrics")


class AdjustmentProposal(TimestampMixin, Base):
    """Human-reviewed proposal generated by deterministic learning."""

    __tablename__ = "adjustment_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    learning_run_id: Mapped[int] = mapped_column(ForeignKey("learning_runs.id"), nullable=False, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    proposal_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_value_json: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    proposed_value_json: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    expected_effect: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), default="Pendiente", nullable=False, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    learning_run: Mapped[LearningRun] = relationship(back_populates="proposals")
    profile: Mapped[ProfessionalProfile] = relationship(back_populates="adjustment_proposals")
    change_history: Mapped[list[ConfigurationChangeHistory]] = relationship(back_populates="proposal")


class ConfigurationChangeHistory(Base):
    """Versioned record for an approved configuration-related change."""

    __tablename__ = "configuration_change_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    proposal_id: Mapped[int | None] = mapped_column(ForeignKey("adjustment_proposals.id"), nullable=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    configuration_area: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    previous_value_json: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    new_value_json: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(120), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    rollback_data_json: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reverted_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    proposal: Mapped[AdjustmentProposal | None] = relationship(back_populates="change_history")
    profile: Mapped[ProfessionalProfile] = relationship(back_populates="configuration_changes")


class SavedView(TimestampMixin, Base):
    """Saved filters and sort order for the strategic inbox."""

    __tablename__ = "saved_views"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_saved_view_profile_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    sort_json: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    profile: Mapped[ProfessionalProfile] = relationship()


class DailyShortlist(TimestampMixin, Base):
    """Manual daily list of jobs to process."""

    __tablename__ = "daily_shortlists"
    __table_args__ = (UniqueConstraint("profile_id", "shortlist_date", name="uq_daily_shortlist_profile_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False, index=True)
    shortlist_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), default="Borrador", nullable=False, index=True)

    profile: Mapped[ProfessionalProfile] = relationship()
    items: Mapped[list[DailyShortlistItem]] = relationship(
        back_populates="shortlist",
        cascade="all, delete-orphan",
    )


class DailyShortlistItem(TimestampMixin, Base):
    """One job planned in a daily shortlist."""

    __tablename__ = "daily_shortlist_items"
    __table_args__ = (
        UniqueConstraint("shortlist_id", "job_id", name="uq_shortlist_job"),
        UniqueConstraint("shortlist_id", "position", name="uq_shortlist_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shortlist_id: Mapped[int] = mapped_column(ForeignKey("daily_shortlists.id"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    priority_id: Mapped[int | None] = mapped_column(ForeignKey("job_priorities.id"), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_action: Mapped[str] = mapped_column(String(120), nullable=False)
    completion_status: Mapped[str] = mapped_column(String(80), default="Pendiente", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    shortlist: Mapped[DailyShortlist] = relationship(back_populates="items")
    job: Mapped[Job] = relationship()
    priority: Mapped[JobPriority | None] = relationship()


class ImportBatch(Base):
    """CSV or manual import batch audit record."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inserted_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(80), default="Creado", nullable=False, index=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    staging_jobs: Mapped[list[ImportStagingJob]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    errors: Mapped[list[JobImportError]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class ImportStagingJob(TimestampMixin, Base):
    """Temporary reviewed job row before confirmed import."""

    __tablename__ = "import_staging_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, nullable=False)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(80), default="Pendiente", nullable=False, index=True)
    validation_errors: Mapped[list[str] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    validation_warnings: Mapped[list[str] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    duplicate_status: Mapped[str] = mapped_column(String(80), default="Pendiente de revision", nullable=False, index=True)
    duplicate_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    user_decision: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    batch: Mapped[ImportBatch] = relationship(back_populates="staging_jobs")
    duplicate_job: Mapped[Job | None] = relationship(foreign_keys=[duplicate_job_id])


class JobImportError(Base):
    """Import validation or processing error."""

    __tablename__ = "job_import_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), nullable=False, index=True)
    staging_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_staging_jobs.id"), nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str] = mapped_column(String(120), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    batch: Mapped[ImportBatch] = relationship(back_populates="errors")
    staging_job: Mapped[ImportStagingJob | None] = relationship()


class JobSource(TimestampMixin, Base):
    """Configured authorized source for manual job captures."""

    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint("name", name="uq_job_source_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    capture_runs: Mapped[list[JobSourceCaptureRun]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    captured_items: Mapped[list[CapturedSourceItem]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class JobSourceCaptureRun(Base):
    """Manual execution of a configured source connector."""

    __tablename__ = "job_source_capture_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("job_sources.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), default="Creado", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    records_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_staged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True, index=True)

    source: Mapped[JobSource | None] = relationship(back_populates="capture_runs")
    import_batch: Mapped[ImportBatch | None] = relationship()
    captured_items: Mapped[list[CapturedSourceItem]] = relationship(
        back_populates="capture_run",
        cascade="all, delete-orphan",
    )


class CapturedSourceItem(Base):
    """Raw item received from an authorized source before human import."""

    __tablename__ = "captured_source_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("job_sources.id"), nullable=True, index=True)
    capture_run_id: Mapped[int | None] = mapped_column(ForeignKey("job_source_capture_runs.id"), nullable=True, index=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True, index=True)
    staging_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_staging_jobs.id"), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    source_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(SQLAlchemyJSON, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="Staged", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    source: Mapped[JobSource | None] = relationship(back_populates="captured_items")
    capture_run: Mapped[JobSourceCaptureRun | None] = relationship(back_populates="captured_items")
    import_batch: Mapped[ImportBatch | None] = relationship()
    staging_job: Mapped[ImportStagingJob | None] = relationship()


class CSVMappingProfile(TimestampMixin, Base):
    """Reusable CSV column mapping profile for a source."""

    __tablename__ = "csv_mapping_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    mapping: Mapped[dict[str, str]] = mapped_column(SQLAlchemyJSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobStatusHistory(Base):
    """Auditable status change for a job."""

    __tablename__ = "job_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    new_status: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    job: Mapped[Job] = relationship(back_populates="status_history", foreign_keys=[job_id])


class JobTag(Base):
    """Reusable job tag."""

    __tablename__ = "job_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    assignments: Mapped[list[JobTagAssignment]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class JobTagAssignment(Base):
    """Association between a job and a tag."""

    __tablename__ = "job_tag_assignments"
    __table_args__ = (UniqueConstraint("job_id", "tag_id", name="uq_job_tag_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("job_tags.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    job: Mapped[Job] = relationship(back_populates="tag_assignments")
    tag: Mapped[JobTag] = relationship(back_populates="assignments")


class ProfessionalProfile(TimestampMixin, Base):
    """Structured professional profile for the user."""

    __tablename__ = "professional_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    professional_title: Mapped[str] = mapped_column(String(300), nullable=False)
    professional_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_city: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    current_province: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    country: Mapped[str] = mapped_column(String(120), default="Ecuador", nullable=False)
    years_total_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    availability_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    willing_to_relocate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    willing_to_travel: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    remote_preference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    experiences: Mapped[list[WorkExperience]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    profile_skills: Mapped[list[ProfileSkill]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    profile_tools: Mapped[list[ProfileTool]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    education_records: Mapped[list[EducationRecord]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    certifications: Mapped[list[Certification]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    target_roles: Mapped[list[TargetRole]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    target_sectors: Mapped[list[TargetSector]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    job_preferences: Mapped[list[JobPreference]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    job_constraints: Mapped[list[JobConstraint]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="profile",
    )
    growth_goals: Mapped[list[GrowthGoal]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    feedback_events: Mapped[list[FeedbackEvent]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    learning_runs: Mapped[list[LearningRun]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    adjustment_proposals: Mapped[list[AdjustmentProposal]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    configuration_changes: Mapped[list[ConfigurationChangeHistory]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class WorkExperience(TimestampMixin, Base):
    """Professional experience attached to a profile."""

    __tablename__ = "work_experiences"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_work_dates"),
        CheckConstraint("people_managed IS NULL OR people_managed >= 0", name="ck_people_managed"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_job_title: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sector: Mapped[str | None] = mapped_column(String(160), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    achievements: Mapped[str | None] = mapped_column(Text, nullable=True)
    people_managed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="experiences")


class Skill(TimestampMixin, Base):
    """Normalized skill catalog entry."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile_skills: Mapped[list[ProfileSkill]] = relationship(back_populates="skill")
    growth_goals: Mapped[list[GrowthGoal]] = relationship(back_populates="target_skill")


class ProfileSkill(TimestampMixin, Base):
    """Assigned skill and self-assessed level for a profile."""

    __tablename__ = "profile_skills"
    __table_args__ = (
        UniqueConstraint("profile_id", "skill_id", name="uq_profile_skill"),
        CheckConstraint("years_experience IS NULL OR years_experience >= 0", name="ck_skill_years"),
        CheckConstraint("last_used_year IS NULL OR last_used_year <= 2100", name="ck_last_used_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(80), nullable=False)
    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    last_used_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interest_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_core_skill: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    self_assessed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="profile_skills")
    skill: Mapped[Skill] = relationship(back_populates="profile_skills")
    evidences: Mapped[list[SkillEvidence]] = relationship(
        back_populates="profile_skill",
        cascade="all, delete-orphan",
    )


class SkillEvidence(TimestampMixin, Base):
    """Evidence supporting a profile skill."""

    __tablename__ = "skill_evidences"
    __table_args__ = (
        CheckConstraint("metric_value IS NULL OR metric_value >= 0", name="ck_evidence_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_skill_id: Mapped[int] = mapped_column(ForeignKey("profile_skills.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    metric_unit: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    profile_skill: Mapped[ProfileSkill] = relationship(back_populates="evidences")


class Tool(TimestampMixin, Base):
    """Normalized software or tool catalog entry."""

    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)

    profile_tools: Mapped[list[ProfileTool]] = relationship(back_populates="tool")


class ProfileTool(TimestampMixin, Base):
    """Assigned tool and self-assessed level for a profile."""

    __tablename__ = "profile_tools"
    __table_args__ = (
        UniqueConstraint("profile_id", "tool_id", name="uq_profile_tool"),
        CheckConstraint("years_experience IS NULL OR years_experience >= 0", name="ck_tool_years"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    tool_id: Mapped[int] = mapped_column(ForeignKey("tools.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(80), nullable=False)
    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="profile_tools")
    tool: Mapped[Tool] = relationship(back_populates="profile_tools")


class EducationRecord(TimestampMixin, Base):
    """Education record attached to a profile."""

    __tablename__ = "education_records"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_education_dates"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    institution: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    degree: Mapped[str] = mapped_column(String(255), nullable=False)
    field_of_study: Mapped[str] = mapped_column(String(255), nullable=False)
    education_level: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="education_records")


class Certification(TimestampMixin, Base):
    """Certification or credential attached to a profile."""

    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint(
            "expiration_date IS NULL OR issue_date IS NULL OR expiration_date >= issue_date",
            name="ck_certification_dates",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_organization: Mapped[str] = mapped_column(String(255), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    credential_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    does_not_expire: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="certifications")


class TargetRole(TimestampMixin, Base):
    """Target role for job search prioritization."""

    __tablename__ = "target_roles"
    __table_args__ = (
        UniqueConstraint("profile_id", "normalized_role_name", name="uq_profile_target_role"),
        CheckConstraint("minimum_salary IS NULL OR minimum_salary >= 0", name="ck_target_salary"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_role_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(80), nullable=False)
    desired_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    minimum_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="target_roles")


class TargetSector(TimestampMixin, Base):
    """Target sector for job search prioritization."""

    __tablename__ = "target_sectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(180), nullable=False)
    priority: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="target_sectors")


class JobPreference(TimestampMixin, Base):
    """Non-mandatory job preferences used for ranking later."""

    __tablename__ = "job_preferences"
    __table_args__ = (
        CheckConstraint("minimum_salary IS NULL OR minimum_salary >= 0", name="ck_pref_min_salary"),
        CheckConstraint("expected_salary IS NULL OR expected_salary >= 0", name="ck_pref_expected_salary"),
        CheckConstraint(
            "maximum_commute_minutes IS NULL OR maximum_commute_minutes >= 0",
            name="ck_pref_commute",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    preferred_cities: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    preferred_provinces: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    accepted_modalities: Mapped[list[str]] = mapped_column(SQLAlchemyJSON, default=list, nullable=False)
    minimum_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expected_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    accepts_shift_work: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepts_weekend_work: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepts_temporary_contract: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    maximum_commute_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_size_preference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="job_preferences")


class JobConstraint(TimestampMixin, Base):
    """Mandatory job search constraint."""

    __tablename__ = "job_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(120), nullable=False)
    operator: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="job_constraints")


class GrowthGoal(TimestampMixin, Base):
    """Professional growth goal tracked by the user."""

    __tablename__ = "growth_goals"
    __table_args__ = (
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100", name="ck_goal_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("professional_profiles.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_skill_id: Mapped[int | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[str] = mapped_column(String(80), nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    profile: Mapped[ProfessionalProfile] = relationship(back_populates="growth_goals")
    target_skill: Mapped[Skill | None] = relationship(back_populates="growth_goals")
