# PostgreSQL Database Setup with Alembic Migrations

LexExtract now uses PostgreSQL as its primary database with Alembic for database schema migrations. This document explains how to set up and use the database with proper migration management.

## Quick Start

1. **Prerequisites**: Docker and Docker Compose installed
2. **Start databases and run migrations**: `./scripts/setup_db.sh`
3. **Run tests**: `python -m pytest tests/`

## Database Configuration

The application uses two PostgreSQL databases:

- **Main Database**: `lexextract` on port 5432
- **Test Database**: `lexextract_test` on port 5433

### Connection URLs

```bash
# Main database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/lexextract

# Test database  
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/lexextract_test
```

## Setup Instructions

### 1. Start PostgreSQL Containers

```bash
# Using the setup script (recommended)
./scripts/setup_db.sh

# Or manually with Docker Compose
docker-compose up -d postgres postgres_test
```

### 2. Set Environment Variables

```bash
export DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/lexextract'
export TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5433/lexextract_test'
```

### 3. Run Database Migrations

The setup script automatically runs migrations, but you can also run them manually:

```bash
# Upgrade to latest migration
docker-compose run --rm fastapi alembic upgrade head

# Check current migration status
docker-compose run --rm fastapi alembic current
```

### 4. Run Tests

```bash
# Run all tests
python -m pytest tests/

# Run only database tests
python -m pytest tests/test_db.py -v
```

## Database Schema

The application defines three main tables:

### Clients Table
- `id` (Primary Key)
- `name` (Required)
- `contact_name`
- `contact_email`
- `created_at`

### Statements Table
- `id` (Primary Key)
- `client_id` (Foreign Key → clients.id)
- `uploaded_at`
- `file_path` (Required)

### Transactions Table
- `id` (Primary Key)
- `statement_id` (Foreign Key → statements.id)
- `date` (Required)
- `payee` (Required)
- `amount` (Required)
- `type` (Required)
- `balance`
- `currency` (Default: GBP)

## Database Migrations with Alembic

LexExtract uses Alembic for database schema version control. This allows for safe, trackable changes to the database structure.

### Migration Commands

#### Using Docker Compose (Recommended)

```bash
# Check current migration status
docker-compose run --rm fastapi alembic current

# Show migration history
docker-compose run --rm fastapi alembic history

# Upgrade to latest migration
docker-compose run --rm fastapi alembic upgrade head

# Upgrade to specific revision
docker-compose run --rm fastapi alembic upgrade <revision_id>

# Downgrade to previous migration
docker-compose run --rm fastapi alembic downgrade -1

# Downgrade to specific revision
docker-compose run --rm fastapi alembic downgrade <revision_id>

# Create new migration (autogenerate from model changes)
docker-compose run --rm fastapi alembic revision --autogenerate -m "Description of changes"

# Create empty migration template
docker-compose run --rm fastapi alembic revision -m "Manual migration description"
```

#### Using the Python Migration Script

```bash
# Check current status
docker-compose run --rm fastapi python scripts/migrate.py current

# Show history
docker-compose run --rm fastapi python scripts/migrate.py history

# Upgrade to latest
docker-compose run --rm fastapi python scripts/migrate.py upgrade

# Create new migration
docker-compose run --rm fastapi python scripts/migrate.py create "Description of changes"
```

### Making Schema Changes

1. **Modify your models** in `app/models.py`
2. **Generate migration**:
   ```bash
   docker-compose run --rm fastapi alembic revision --autogenerate -m "Add new field to User model"
   ```
3. **Review the generated migration** in `alembic/versions/`
4. **Apply the migration**:
   ```bash
   docker-compose run --rm fastapi alembic upgrade head
   ```

### Migration Best Practices

- **Always review** generated migrations before applying them
- **Test migrations** on a copy of production data first
- **Use descriptive messages** for migration names
- **Never edit** applied migrations; create new ones instead
- **Backup your database** before applying migrations in production

## Development Workflow

1. **Start databases and apply migrations**: `./scripts/setup_db.sh`
2. **Develop with FastAPI**: The app automatically connects to PostgreSQL
3. **Make model changes**: Edit `app/models.py`
4. **Generate migrations**: `docker-compose run --rm fastapi alembic revision --autogenerate -m "description"`
5. **Apply migrations**: `docker-compose run --rm fastapi alembic upgrade head`
6. **Run tests**: Tests use the separate test database
7. **Stop databases**: `docker-compose down`

## Troubleshooting

### Database Connection Issues

```bash
# Check if containers are running
docker-compose ps

# Check database logs
docker-compose logs postgres
docker-compose logs postgres_test

# Restart containers
docker-compose down && docker-compose up -d
```

### Migration Issues

```bash
# Check current migration status
docker-compose run --rm fastapi alembic current

# Show migration history
docker-compose run --rm fastapi alembic history

# Check if database is out of sync
docker-compose run --rm fastapi alembic check

# Manual migration rollback (DANGEROUS - backup first!)
docker-compose run --rm fastapi alembic downgrade -1

# Reset to specific migration
docker-compose run --rm fastapi alembic downgrade <revision_id>
```

### Schema Conflicts

If you encounter migration conflicts:

1. **Check the migration history**:
   ```bash
   docker-compose run --rm fastapi alembic history
   ```

2. **Create a merge migration**:
   ```bash
   docker-compose run --rm fastapi alembic merge -m "Merge conflicting migrations" <rev1> <rev2>
   ```

3. **Manual resolution**: Edit the migration file if needed

### Test Database Issues

```bash
# Reset test database
docker-compose restart postgres_test

# Apply migrations to test database
TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5433/lexextract_test' \
  docker-compose run --rm fastapi alembic upgrade head

# Manual database access
docker-compose exec postgres_test psql -U postgres -d lexextract_test
```

## Production Deployment

For production, use a managed PostgreSQL service or configure your own PostgreSQL instance:

```bash
# Production database URL example
export DATABASE_URL='postgresql+asyncpg://user:password@prod-db-host:5432/lexextract'
```

### Production Migration Steps

1. **Backup your database** before applying migrations
2. **Test migrations** on a staging environment first
3. **Apply migrations**:
   ```bash
   # In production environment
   alembic upgrade head
   ```
4. **Verify the application** starts successfully

### Production Database Requirements

Ensure your production database has:
- Appropriate connection limits
- Backup and monitoring configured  
- SSL/TLS encryption enabled
- Proper user permissions set
- **Alembic migration history table** (`alembic_version`) maintained 