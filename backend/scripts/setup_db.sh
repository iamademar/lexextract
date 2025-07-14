#!/bin/bash

# Setup script for PostgreSQL databases
set -e

echo "🐘 Setting up PostgreSQL databases for LexExtract..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start PostgreSQL containers
echo "🚀 Starting PostgreSQL containers..."
docker-compose up -d postgres postgres_test

# Wait for databases to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 10

# Check if databases are ready
echo "🔍 Checking database connectivity..."
until docker-compose exec postgres pg_isready -U postgres >/dev/null 2>&1; do
    echo "   Main database not ready, waiting..."
    sleep 2
done

until docker-compose exec postgres_test pg_isready -U postgres >/dev/null 2>&1; do
    echo "   Test database not ready, waiting..."
    sleep 2
done

echo "✅ PostgreSQL databases are ready!"

# Run database migrations
echo ""
echo "🔄 Running database migrations..."
docker-compose run --rm fastapi alembic upgrade head
echo "✅ Database migrations completed!"

echo ""
echo "📋 Database Information:"
echo "  Main Database: postgresql://postgres:password@localhost:5432/lexextract"
echo "  Test Database: postgresql://postgres:password@localhost:5433/lexextract_test"
echo ""
echo "🔧 Environment Variables:"
echo "  export DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/lexextract'"
echo "  export TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5433/lexextract_test'"
echo ""
echo "🗃️ Migration Commands:"
echo "  # Check current migration status:"
echo "  docker-compose run --rm fastapi alembic current"
echo ""
echo "  # Create new migration:"
echo "  docker-compose run --rm fastapi alembic revision --autogenerate -m 'description'"
echo ""
echo "  # Upgrade to latest migration:"
echo "  docker-compose run --rm fastapi alembic upgrade head"
echo ""
echo "  # Downgrade to previous migration:"
echo "  docker-compose run --rm fastapi alembic downgrade -1"
echo ""
echo "  # Using the Python migration script:"
echo "  docker-compose run --rm fastapi python scripts/migrate.py current"
echo "  docker-compose run --rm fastapi python scripts/migrate.py upgrade"
echo "  docker-compose run --rm fastapi python scripts/migrate.py create 'migration description'"
echo ""
echo "🧪 To run tests:"
echo "  python -m pytest tests/"
echo ""
echo "🛑 To stop databases:"
echo "  docker-compose down" 