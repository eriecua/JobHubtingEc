from __future__ import annotations

from pathlib import Path

import pytest

from app.config import get_settings, load_profile_config, load_scoring_weights, load_yaml_file


def test_load_yaml_file_reads_mapping(tmp_path: Path) -> None:
    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("name: Radar\nphase: 1\n", encoding="utf-8")

    data = load_yaml_file(yaml_path)

    assert data == {"name": "Radar", "phase": 1}


def test_profile_yaml_loads() -> None:
    profile = load_profile_config()

    assert profile["profile_status"] == "example"
    assert "target_roles" in profile


def test_scoring_weights_sum_100() -> None:
    weights = load_scoring_weights()

    assert sum(weights.model_dump().values()) == 100


def test_scoring_weights_reject_invalid_total(tmp_path: Path) -> None:
    weights_path = tmp_path / "weights.yaml"
    weights_path.write_text(
        "\n".join(
            [
                "skills: 20",
                "experience: 15",
                "target_role: 15",
                "growth: 10",
                "salary: 10",
                "location: 10",
                "company_sector: 10",
                "recency: 5",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sum 100"):
        load_scoring_weights(weights_path)


def test_relative_database_url_resolves_inside_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("RADAR_DATABASE_URL=sqlite:///data/custom.db\n", encoding="utf-8")
    monkeypatch.delenv("RADAR_DATABASE_URL", raising=False)
    monkeypatch.delenv("RADAR_DATA_DIR", raising=False)
    monkeypatch.delenv("RADAR_CONFIG_DIR", raising=False)

    settings = get_settings(project_root=tmp_path, env_file=env_path)

    assert settings.database_path == tmp_path / "data" / "custom.db"
