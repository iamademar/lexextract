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
echo ""
echo "📋 Database Information:"
echo "  Main Database: postgresql://postgres:password@localhost:5432/lexextract"
echo "  Test Database: postgresql://postgres:password@localhost:5433/lexextract_test"
echo ""
echo "🔧 Environment Variables:"
echo "  export DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/lexextract'"
echo "  export TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5433/lexextract_test'"
echo ""
echo "🧪 To run tests:"
echo "  python -m pytest tests/"
echo ""
echo "🛑 To stop databases:"
echo "  docker-compose down" 