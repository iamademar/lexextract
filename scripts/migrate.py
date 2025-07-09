#!/usr/bin/env python3
"""
Migration management script for LexExtract

This script provides convenience functions for managing database migrations
using Alembic programmatically.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic.config import Config
from alembic import command


def get_alembic_config():
    """Get Alembic configuration"""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    alembic_ini_path = project_root / "alembic.ini"
    
    config = Config(str(alembic_ini_path))
    return config


def upgrade(revision="head"):
    """Upgrade database to a specific revision"""
    print(f"Upgrading database to revision: {revision}")
    config = get_alembic_config()
    command.upgrade(config, revision)
    print("Migration upgrade completed successfully!")


def downgrade(revision):
    """Downgrade database to a specific revision"""
    print(f"Downgrading database to revision: {revision}")
    config = get_alembic_config()
    command.downgrade(config, revision)
    print("Migration downgrade completed successfully!")


def current():
    """Show current migration revision"""
    print("Current database revision:")
    config = get_alembic_config()
    command.current(config, verbose=True)


def history():
    """Show migration history"""
    print("Migration history:")
    config = get_alembic_config()
    command.history(config, verbose=True)


def create_migration(message, autogenerate=True):
    """Create a new migration"""
    print(f"Creating new migration: {message}")
    config = get_alembic_config()
    if autogenerate:
        command.revision(config, message=message, autogenerate=True)
    else:
        command.revision(config, message=message)
    print("Migration created successfully!")


def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate.py <command> [args]")
        print("Commands:")
        print("  upgrade [revision]  - Upgrade to head or specific revision")
        print("  downgrade <revision> - Downgrade to specific revision")
        print("  current             - Show current revision")
        print("  history             - Show migration history")
        print("  create <message>    - Create new migration")
        return

    command_name = sys.argv[1]
    
    try:
        if command_name == "upgrade":
            revision = sys.argv[2] if len(sys.argv) > 2 else "head"
            upgrade(revision)
        elif command_name == "downgrade":
            if len(sys.argv) < 3:
                print("Error: downgrade requires a revision argument")
                return
            downgrade(sys.argv[2])
        elif command_name == "current":
            current()
        elif command_name == "history":
            history()
        elif command_name == "create":
            if len(sys.argv) < 3:
                print("Error: create requires a message argument")
                return
            create_migration(sys.argv[2])
        else:
            print(f"Unknown command: {command_name}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main() 