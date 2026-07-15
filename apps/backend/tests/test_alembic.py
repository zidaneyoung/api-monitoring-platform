from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData

from app.database import Base


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_configuration_loads() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert Path(scripts.dir).resolve() == BACKEND_ROOT / "alembic"
    assert scripts.get_bases()
    assert scripts.get_current_head() is not None


def test_alembic_ini_does_not_hardcode_database_url() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    assert config.get_main_option("sqlalchemy.url") is None


def test_application_metadata_is_available_to_alembic() -> None:
    assert isinstance(Base.metadata, MetaData)
