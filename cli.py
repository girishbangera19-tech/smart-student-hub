"""Database diagnostic commands.

    flask check-db     shows which tables/columns are missing (changes nothing)
    flask repair-db    creates missing tables and adds missing columns (never deletes data)

Use these if a page fails to save because your database is older than the code.
The preferred route is still:  flask db migrate  then  flask db upgrade.
"""
import click
from flask import current_app
from sqlalchemy import inspect, text

from extensions import db


def _differences():
    """Return (missing_tables, {table: [missing Column objects]})."""
    import models  # noqa: F401  (makes sure every model is registered)

    inspector = inspect(db.engine)
    existing = set(inspector.get_table_names())
    missing_tables, missing_columns = [], {}
    for name, table in db.metadata.tables.items():
        if name not in existing:
            missing_tables.append(name)
            continue
        have = {c["name"] for c in inspector.get_columns(name)}
        lacking = [c for c in table.columns if c.name not in have]
        if lacking:
            missing_columns[name] = lacking
    return missing_tables, missing_columns


def register_commands(app):
    @app.cli.command("check-db")
    def check_db():
        """Compare the database with the models (read only)."""
        click.echo(f"Database: {db.engine.url}")
        tables, columns = _differences()
        if not tables and not columns:
            click.echo("OK: every table and column the code expects exists.")
            return
        for t in tables:
            click.echo(f"MISSING TABLE : {t}")
        for t, cols in columns.items():
            for c in cols:
                click.echo(f"MISSING COLUMN: {t}.{c.name}")
        click.echo("\nFix with:  flask repair-db   (safe: never deletes data)")

    @app.cli.command("repair-db")
    def repair_db():
        """Create missing tables and add missing columns. Existing data is untouched."""
        messages = apply_repairs()
        click.echo("\n".join(messages) if messages else "Nothing to repair.")
        if messages:
            click.echo("Done. Run  flask check-db  to confirm.")


def apply_repairs():
    """Additive-only schema repair. Returns a list of messages describing what was done."""
    tables, columns = _differences()
    done = []
    for name in tables:
        db.metadata.tables[name].create(db.engine, checkfirst=True)
        done.append(f"created table {name}")
    for name, cols in columns.items():
        for col in cols:
            if not col.nullable and col.default is None and col.server_default is None:
                done.append(f"SKIPPED {name}.{col.name}: NOT NULL without a default; use flask db migrate")
                continue
            ddl_type = col.type.compile(dialect=db.engine.dialect)
            with db.engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{name}" ADD COLUMN "{col.name}" {ddl_type}'))
            done.append(f"added column {name}.{col.name}")
    return done


def auto_repair_on_startup(app):
    """Safety net for existing installs: if the database already exists but is older than
    the code (for example after an update), add what is missing. Never deletes anything,
    and never touches a brand-new empty database (flask db upgrade handles that)."""
    try:
        with app.app_context():
            if "users" not in inspect(db.engine).get_table_names():
                return
            for message in apply_repairs():
                app.logger.warning("Database auto-repair: %s", message)
    except Exception:  # never stop the app from starting because of this
        app.logger.exception("Database auto-repair could not run (try: flask check-db)")