"""Configuration helpers for Radar Laboral Adaptativo."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_DATA_DIR = Path("data")
DEFAULT_DATABASE_NAME = "radar_laboral.db"


class Settings(BaseModel):
    """Runtime settings loaded from environment variables and defaults."""

    app_name: str = "Radar Laboral Adaptativo"
    project_root: Path = Field(default_factory=lambda: PROJECT_ROOT)
    config_dir: Path = DEFAULT_CONFIG_DIR
    data_dir: Path = DEFAULT_DATA_DIR
    database_url: str

    @property
    def database_path(self) -> Path | None:
        """Return the local SQLite database path when using a file database."""

        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix) or self.database_url == "sqlite:///:memory:":
            return None
        return Path(self.database_url.removeprefix(prefix))


class ScoringWeights(BaseModel):
    """Configurable scoring weights for future recommendation logic."""

    skills: int
    experience: int
    target_role: int
    growth: int
    salary: int
    location: int | None = None
    location_modality: int | None = None
    company_sector: int
    recency: int

    @model_validator(mode="after")
    def validate_total(self) -> "ScoringWeights":
        """Validate that all scoring weights add up to 100 points."""

        if self.location is None and self.location_modality is None:
            raise ValueError("Scoring weights must define location or location_modality.")
        data = BaseModel.model_dump(self)
        if data.get("location_modality") is None:
            data["location_modality"] = data.get("location")
        if data.get("location") is None:
            data["location"] = data.get("location_modality")
        total = (
            data["skills"]
            + data["experience"]
            + data["target_role"]
            + data["growth"]
            + data["salary"]
            + data["location_modality"]
            + data["company_sector"]
            + data["recency"]
        )
        if total != 100:
            raise ValueError(f"Scoring weights must sum 100, got {total}.")
        self.location = data["location"]
        self.location_modality = data["location_modality"]
        return self

    def phase4_weights(self) -> dict[str, int]:
        """Return the eight Phase 4 dimensions with normalized names."""

        return {
            "skills": self.skills,
            "experience": self.experience,
            "target_role": self.target_role,
            "growth": self.growth,
            "salary": self.salary,
            "location_modality": self.location_modality or self.location or 0,
            "company_sector": self.company_sector,
            "recency": self.recency,
        }

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Dump weights in the historical public shape without double-counting location."""

        data = super().model_dump(*args, **kwargs)
        data.pop("location_modality", None)
        if data.get("location") is None:
            data["location"] = self.location_modality
        return data


class ProfileCompletenessWeights(BaseModel):
    """Configurable weights for profile completeness scoring."""

    basic_professional_data: int
    professional_summary: int
    work_experience: int
    skills: int
    skills_with_evidence: int
    tools: int
    education: int
    certifications: int
    target_roles: int
    preferences_and_constraints: int

    @model_validator(mode="after")
    def validate_total(self) -> "ProfileCompletenessWeights":
        """Validate that all completeness weights add up to 100 percent."""

        total = sum(self.model_dump().values())
        if total != 100:
            raise ValueError(f"Profile completeness weights must sum 100, got {total}.")
        return self


class PriorityWeights(BaseModel):
    """Configurable weights for strategic prioritization."""

    compatibility: int
    confidence: int
    urgency: int
    strategic_alignment: int
    growth_value: int
    salary_location_fit: int
    actionability: int
    application_effort: int

    @model_validator(mode="after")
    def validate_total(self) -> "PriorityWeights":
        """Validate that priority weights add up to 100 points."""

        total = sum(self.model_dump().values())
        if total != 100:
            raise ValueError(f"Priority weights must sum 100, got {total}.")
        return self


class FeedbackLearningConfig(BaseModel):
    """Validated configuration for controlled feedback learning."""

    learning_version: str
    signal_value_limits: dict[str, float]
    feedback_signal_weights: dict[str, dict[str, float]]
    event_categories: list[str]
    event_sources: list[str]
    application_outcome_types: list[str]
    learning_statuses: list[str]
    metric_scopes: list[str]
    proposal_types: list[str]
    proposal_statuses: list[str]
    risk_levels: list[str]
    learning_thresholds: dict[str, int]
    feedback_recency: dict[str, float]
    priority_ranges: list[dict[str, Any]]

    @model_validator(mode="after")
    def validate_learning_config(self) -> "FeedbackLearningConfig":
        """Validate safe bounds for deterministic learning signals."""

        lower = float(self.signal_value_limits.get("minimum", -2.0))
        upper = float(self.signal_value_limits.get("maximum", 2.0))
        if lower >= upper:
            raise ValueError("Feedback signal limits must define minimum lower than maximum.")
        for group, weights in self.feedback_signal_weights.items():
            if not weights:
                raise ValueError(f"Feedback signal weight group is empty: {group}.")
            for name, value in weights.items():
                numeric = float(value)
                if numeric < lower or numeric > upper:
                    raise ValueError(f"Feedback signal weight out of bounds: {group}.{name}.")
        for key, value in self.learning_thresholds.items():
            if int(value) <= 0:
                raise ValueError(f"Learning threshold must be positive: {key}.")
        for key, value in self.feedback_recency.items():
            numeric = float(value)
            if numeric <= 0 or numeric > 1:
                raise ValueError(f"Feedback recency value must be in (0, 1]: {key}.")
        required_catalogs = [
            self.event_categories,
            self.event_sources,
            self.application_outcome_types,
            self.learning_statuses,
            self.metric_scopes,
            self.proposal_types,
            self.proposal_statuses,
            self.risk_levels,
        ]
        if any(not values for values in required_catalogs):
            raise ValueError("Feedback learning catalogs cannot be empty.")
        return self


def load_env_file(env_path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs from a .env file without overriding values."""

    path = env_path or PROJECT_ROOT / ".env"
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_sqlite_url(database_path: Path) -> str:
    """Build a SQLAlchemy SQLite URL from a database path."""

    return f"sqlite:///{database_path.as_posix()}"


def normalize_database_url(database_url: str, project_root: Path) -> str:
    """Resolve relative SQLite database URLs from the project root."""

    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url == "sqlite:///:memory:":
        return database_url

    raw_path = database_url.removeprefix(prefix)
    if raw_path.startswith("file:"):
        return database_url

    database_path = Path(raw_path)
    if database_path.is_absolute():
        return database_url

    return build_sqlite_url(project_root / database_path)


def get_settings(project_root: Path | None = None, env_file: Path | None = None) -> Settings:
    """Load application settings and ensure required local directories exist."""

    root = project_root or PROJECT_ROOT
    load_env_file(env_file or root / ".env")

    config_dir = Path(os.getenv("RADAR_CONFIG_DIR", str(DEFAULT_CONFIG_DIR)))
    data_dir = Path(os.getenv("RADAR_DATA_DIR", str(DEFAULT_DATA_DIR)))
    resolved_data_dir = root / data_dir
    resolved_data_dir.mkdir(parents=True, exist_ok=True)

    database_url = os.getenv(
        "RADAR_DATABASE_URL",
        build_sqlite_url(resolved_data_dir / DEFAULT_DATABASE_NAME),
    )
    database_url = normalize_database_url(database_url, root)

    return Settings(
        project_root=root,
        config_dir=config_dir,
        data_dir=data_dir,
        database_url=database_url,
    )


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Read a YAML file and return a dictionary."""

    try:
        with path.open("r", encoding="utf-8") as yaml_file:
            data = yaml.safe_load(yaml_file) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML file: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def load_profile_config(path: Path | None = None) -> dict[str, Any]:
    """Load the professional profile configuration file."""

    profile_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "profile.yaml"
    return load_yaml_file(profile_path)


def load_scoring_weights(path: Path | None = None) -> ScoringWeights:
    """Load and validate scoring weights from YAML."""

    weights_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "scoring_weights.yaml"
    data = load_yaml_file(weights_path)
    try:
        return ScoringWeights(**data)
    except ValidationError as exc:
        detail = exc.errors()[0].get("msg", str(exc))
        raise ValueError(
            f"Invalid scoring weights configuration: {weights_path}. {detail}"
        ) from exc


def load_profile_catalogs(path: Path | None = None) -> dict[str, Any]:
    """Load profile catalogs and alias configuration from YAML."""

    catalogs_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "profile_catalogs.yaml"
    return load_yaml_file(catalogs_path)


def load_profile_completeness_weights(path: Path | None = None) -> ProfileCompletenessWeights:
    """Load and validate profile completeness weights from YAML."""

    weights_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "profile_completeness.yaml"
    data = load_yaml_file(weights_path)
    try:
        return ProfileCompletenessWeights(**data)
    except ValidationError as exc:
        detail = exc.errors()[0].get("msg", str(exc))
        raise ValueError(
            f"Invalid profile completeness configuration: {weights_path}. {detail}"
        ) from exc


def load_job_import_config(path: Path | None = None) -> dict[str, Any]:
    """Load job import catalogs, aliases and limits from YAML."""

    config_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "job_import.yaml"
    config = load_yaml_file(config_path)
    required_keys = [
        "job_statuses",
        "review_statuses",
        "data_quality_statuses",
        "modalities",
        "employment_types",
        "salary_periods",
        "currencies",
        "column_aliases",
        "duplicate_thresholds",
        "import_limits",
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ValueError(f"Invalid job import configuration. Missing: {', '.join(missing)}")
    return config


def load_compatibility_config(path: Path | None = None) -> dict[str, Any]:
    """Load deterministic compatibility scoring configuration."""

    config_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "compatibility_scoring.yaml"
    config = load_yaml_file(config_path)
    required_keys = [
        "scoring_version",
        "weights",
        "missing_data_policy",
        "required_markers",
        "desired_markers",
        "recommendation_thresholds",
        "job_families",
        "experience_bands",
        "recency_days",
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ValueError(f"Invalid compatibility configuration. Missing: {', '.join(missing)}")
    weights = ScoringWeights(**config["weights"])
    config["weights"] = weights.phase4_weights()
    for policy_name, policy in config["missing_data_policy"].items():
        for key in ["neutral_score", "confidence"]:
            value = float(policy[key])
            if value < 0 or value > 1:
                raise ValueError(f"Invalid missing data policy value for {policy_name}.{key}.")
    thresholds = config["recommendation_thresholds"]
    ordered = [
        thresholds["high_match"],
        thresholds["good_match"],
        thresholds["exploratory"],
        thresholds["low_match"],
    ]
    if ordered != sorted(ordered, reverse=True):
        raise ValueError("Recommendation thresholds must be ordered from high to low.")
    return config


def load_priority_config(path: Path | None = None) -> dict[str, Any]:
    """Load and validate strategic prioritization configuration."""

    config_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "priority_strategy.yaml"
    config = load_yaml_file(config_path)
    required_keys = [
        "prioritization_version",
        "priority_weights",
        "priority_thresholds",
        "urgency",
        "daily_mix",
        "daily_inbox",
        "wip_limits",
        "stale_decisions",
        "actions",
        "priority_buckets",
        "decision_sources",
        "application_effort",
        "saved_view_filters",
        "saved_view_sort_fields",
        "decision_reasons",
        "application_statuses",
        "shortlist_statuses",
        "shortlist_item_statuses",
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ValueError(f"Invalid priority configuration. Missing: {', '.join(missing)}")
    weights = PriorityWeights(**config["priority_weights"])
    config["priority_weights"] = weights.model_dump()
    thresholds = config["priority_thresholds"]
    ordered = [thresholds["critical"], thresholds["high"], thresholds["medium"], thresholds["low"]]
    if ordered != sorted(ordered, reverse=True):
        raise ValueError("Priority thresholds must be ordered from critical to low.")
    for name, value in config["daily_mix"].items():
        if float(value) < 0 or float(value) > 1:
            raise ValueError(f"Daily mix value must be between 0 and 1: {name}.")
    for group_name in ["wip_limits", "stale_decisions"]:
        for name, value in config[group_name].items():
            if int(value) <= 0:
                raise ValueError(f"{group_name}.{name} must be positive.")
    for name, value in config["daily_inbox"].items():
        if int(value) <= 0:
            raise ValueError(f"daily_inbox.{name} must be positive.")
    for name, value in config["application_effort"].items():
        if float(value) < 0 or float(value) > 1:
            raise ValueError(f"Application effort value must be between 0 and 1: {name}.")
    for action in config["actions"]:
        if not isinstance(action, str) or not action.strip():
            raise ValueError("Priority actions must be non-empty text values.")
    if not config["saved_view_filters"] or not config["saved_view_sort_fields"]:
        raise ValueError("Saved view filter and sort catalogs cannot be empty.")
    return config


def load_feedback_learning_config(path: Path | None = None) -> dict[str, Any]:
    """Load and validate deterministic feedback learning configuration."""

    config_path = path or PROJECT_ROOT / DEFAULT_CONFIG_DIR / "feedback_learning.yaml"
    data = load_yaml_file(config_path)
    try:
        return FeedbackLearningConfig(**data).model_dump()
    except ValidationError as exc:
        detail = exc.errors()[0].get("msg", str(exc))
        raise ValueError(
            f"Invalid feedback learning configuration: {config_path}. {detail}"
        ) from exc
