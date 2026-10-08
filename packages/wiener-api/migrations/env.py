from logging.config import fileConfig

from sqlalchemy import Enum, engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from wiener_api.db import Base
from wiener_api.models import Run, RunArtifact, RunEventRow, RunIntent, RunTask  # noqa: F401
from wiener_api.settings import settings

target_metadata = Base.metadata

# The URL comes from Settings, never from alembic.ini — the same rule mendel-api's env.py
# states: two places that decide where the database lives is two answers to that question,
# and the one in the .ini is the one that gets forgotten in an environment.
config.set_main_option("sqlalchemy.url", settings.database_url)


def _enum_checks() -> set[str]:
    """The CHECKs the models build from an enum (`models._one_of`), by name."""
    return {
        f"ck_{table.name}_{column.type.name}"
        for table in target_metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Enum) and column.type.create_constraint
    }


ENUM_CHECKS = _enum_checks()


def include_object(object, name, type_, reflected, compare_to):  # noqa: A002 — alembic's names
    """**`alembic check` does not see a CHECK that an `Enum` type creates** as part of the
    model, so it reports each one in the database as removed (issue 274). Those are left out
    here; `test_each_check_names_exactly_its_enum` compares them, by name and by value."""
    return not (type_ == "check_constraint" and reflected and name in ENUM_CHECKS)


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
