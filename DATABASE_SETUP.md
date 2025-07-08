# PostgreSQL Database Setup

LexExtract now uses PostgreSQL as its primary database. This document explains how to set up and use the database.

## Quick Start

1. **Prerequisites**: Docker and Docker Compose installed
2. **Start databases**: `./scripts/setup_db.sh`
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

### 3. Run Tests

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

## Development Workflow

1. **Start databases**: `./scripts/setup_db.sh`
2. **Develop with FastAPI**: The app automatically connects to PostgreSQL
3. **Run tests**: Tests use the separate test database
4. **Stop databases**: `docker-compose down`

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

### Test Database Issues

```bash
# Reset test database
docker-compose restart postgres_test

# Manual database access
docker-compose exec postgres_test psql -U postgres -d lexextract_test
```

## Production Deployment

For production, use a managed PostgreSQL service or configure your own PostgreSQL instance:

```bash
# Production database URL example
export DATABASE_URL='postgresql+asyncpg://user:password@prod-db-host:5432/lexextract'
```

Ensure your production database has:
- Appropriate connection limits
- Backup and monitoring configured
- SSL/TLS encryption enabled
- Proper user permissions set 