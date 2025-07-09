# LexExtract

A standalone, secure web application for UK law firms to upload PDF bank statements, extract structured transaction data into CSV, and ask natural-language questions via a chat interface.

## 🏗️ Architecture

- **Backend**: FastAPI (Python) with PostgreSQL database
- **OCR**: PaddleOCR for PDF text extraction
- **LLM**: Mistral 7B for natural language chat interface
- **Deployment**: Docker containerized services

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd LexExtract
   ```

2. **Create environment file**
   ```bash
   cp env.example .env
   ```

3. **Start the application**
   ```bash
   docker-compose up --build -d
   ```

4. **Verify setup**
   ```bash
   curl http://localhost:8000/health
   ```

## 🔄 Development Workflow

Follow this workflow when making database schema changes:

1. **Start databases and apply migrations**
   ```bash
   ./scripts/setup_db.sh
   ```

2. **Make model changes**
   ```bash
   # Edit your SQLAlchemy models
   vim app/models.py
   ```

3. **Generate migration**
   ```bash
   docker-compose run --rm fastapi alembic revision --autogenerate -m "description"
   ```

4. **Apply migration**
   ```bash
   docker-compose run --rm fastapi alembic upgrade head
   ```

5. **Test your changes**
   ```bash
   docker-compose run --rm fastapi pytest
   ```

## 📋 Quick Commands

### Docker Management
```bash
# Start all services
docker-compose up -d

# Build and start services
docker-compose up --build -d

# View running services
docker-compose ps

# Stop all services
docker-compose down

# Restart services
docker-compose restart

# Restart specific service
docker-compose restart fastapi
```

### Logs and Monitoring
```bash
# View all logs
docker-compose logs

# View FastAPI logs
docker-compose logs fastapi

# View PostgreSQL logs
docker-compose logs postgres

# Follow logs in real-time
docker-compose logs -f fastapi
```

### Database Access
```bash
# Connect to main database
docker-compose exec postgres psql -U postgres -d lexextract

# Connect to test database
docker-compose exec postgres_test psql -U postgres -d lexextract_test

# List tables
docker-compose exec postgres psql -U postgres -d lexextract -c "\dt"

# View table structure
docker-compose exec postgres psql -U postgres -d lexextract -c "\d clients"
```

### Development
```bash
# Run tests
docker-compose exec fastapi pytest

# Access FastAPI container shell
docker-compose exec fastapi bash

# View container resources
docker stats

# Check current status
docker-compose run --rm fastapi alembic current

# Create new migration
docker-compose run --rm fastapi alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose run --rm fastapi alembic upgrade head

# Show history
docker-compose run --rm fastapi alembic history
```

## 🌐 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **FastAPI API** | http://localhost:8000 | Main application API |
| **API Documentation** | http://localhost:8000/docs | Interactive Swagger UI |
| **Health Check** | http://localhost:8000/health | Application health status |
| **PostgreSQL (Main)** | localhost:5432 | Main database (postgres/password) |
| **PostgreSQL (Test)** | localhost:5433 | Test database (postgres/password) |

## 📁 Project Structure

```
LexExtract/
├── app/                    # FastAPI application
│   ├── __init__.py
│   ├── main.py            # FastAPI app entry point
│   ├── db.py              # Database configuration
│   └── models.py          # SQLAlchemy models
├── scripts/               # Setup and utility scripts
├── tests/                 # Test files
├── uploads/               # PDF file uploads (mounted volume)
├── exports/               # CSV exports (mounted volume)
├── docker-compose.yml     # Docker services configuration
├── Dockerfile            # FastAPI container definition
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables
```

## 🔧 Configuration

### Environment Variables

Copy `env.example` to `.env` and configure:

```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/lexextract
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@postgres_test:5432/lexextract_test

# Development Settings
DEBUG=True
ENVIRONMENT=development

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_HOURS=1
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# File Storage
UPLOAD_DIR=/var/app/data/uploads
EXPORT_DIR=/var/app/data/exports
```

## 🗄️ Database Schema

The application uses three main tables:

- **`clients`** - Law firm client information
- **`statements`** - Uploaded bank statement metadata
- **`transactions`** - Extracted transaction data

## 🧪 Testing

```bash
# Run all tests
docker-compose exec fastapi pytest

# Run with coverage
docker-compose exec fastapi pytest --cov=app

# Run specific test file
docker-compose exec fastapi pytest tests/test_db.py
```

## 📊 API Endpoints (Planned)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| POST | `/auth/login` | User authentication |
| POST | `/upload/statement` | Upload PDF statement |
| POST | `/process/statement` | Process PDF with OCR |
| GET | `/download/csv/{id}` | Download CSV export |
| POST | `/chat/message` | Chat with AI about statements |
| GET | `/history/sessions` | List chat sessions |

## 🔒 Security Features

- Non-root user in Docker containers
- JWT-based authentication (planned)
- Input validation and sanitization
- Secure file upload handling
- Database connection pooling

## 🚧 Development Status

This is a 2-week MVP demo build. Current status:

- ✅ Docker containerization
- ✅ Database setup and models
- ✅ FastAPI application foundation
- ⏳ File upload endpoints
- ⏳ OCR processing pipeline
- ⏳ Chat interface
- ⏳ Authentication system

## 📝 License

Proprietary license - All rights reserved.

## 🤝 Support

For development questions or issues, please contact the development team.

---

**Note**: This application is designed for demo purposes and requires additional security hardening for production use. 