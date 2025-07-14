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

## 🔍 OCR Implementation

### PaddleOCR Integration
LexExtract uses **PaddleOCR** for robust PDF text extraction with memory-efficient processing:

- **Multi-format support**: Handles various PDF layouts and formats
- **Memory optimization**: Intelligent zoom scaling prevents out-of-memory crashes
- **Quality preservation**: Maintains text extraction accuracy while managing resources
- **Error handling**: Graceful fallback for corrupted or problematic files

### Memory-Efficient Processing
Key optimizations implemented:

- **Dynamic zoom calculation**: Automatically scales large pages to safe processing limits
- **Pixmap size limits**: Prevents excessive memory usage during image conversion  
- **Progressive fallback**: Reduces resolution for oversized documents while preserving readability
- **Memory cleanup**: Explicit resource management for large image processing

### Usage Example
```bash
# Upload and process a PDF statement
curl -X POST "http://localhost:8000/upload/statement?client_id=1" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@bank-statement.pdf"

# Response includes OCR results
{
  "statement_id": 123,
  "pages_processed": 2,
  "ocr_preview": "Your Bank Account Statement..."
}
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
│   ├── models.py          # SQLAlchemy models
│   └── services/          # Business logic services
│       ├── __init__.py
│       └── ocr.py         # OCR processing with PaddleOCR
├── alembic/               # Database migrations
│   ├── env.py
│   └── versions/          # Migration files
├── scripts/               # Setup and utility scripts
│   └── setup_db.sh       # Database initialization
├── tests/                 # Comprehensive test suite
│   ├── test_upload_with_ocr.py  # Upload & OCR integration tests
│   ├── test_db.py         # Database tests
│   ├── test_imports.py    # Import verification
│   └── sample_data/       # Test PDF files
├── data/                  # Docker volume mounts
│   ├── uploads/           # PDF file uploads
│   └── exports/           # CSV exports (planned)
├── docker-compose.yml     # Docker services configuration
├── Dockerfile            # FastAPI container definition
├── requirements.txt      # Python dependencies
├── pytest.ini           # Test configuration
├── alembic.ini           # Database migration config
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

### Dependencies
Key Python packages included:
- **FastAPI** - Web framework and API
- **SQLAlchemy** - Database ORM with async support
- **PaddleOCR** - OCR processing engine
- **PyMuPDF** - PDF manipulation and image extraction
- **PostgreSQL drivers** - Database connectivity
- **Pytest** - Testing framework with async support

## 🗄️ Database Schema

The application uses three main tables:

- **`clients`** - Law firm client information
- **`statements`** - Uploaded bank statement metadata
- **`transactions`** - Extracted transaction data

## 🧪 Testing

### Test Suite Overview
The application includes a comprehensive test suite covering:

- **Upload & OCR Integration**: Real PDF processing with memory-efficient OCR
- **Database Operations**: Statement storage and client validation  
- **Error Handling**: Invalid files, large files, corrupted PDFs
- **Input Validation**: MIME types, file sizes, client verification

### Running Tests

```bash
# Run all tests (17 tests total)
docker-compose exec fastapi pytest

# Run with coverage
docker-compose exec fastapi pytest --cov=app

# Run specific test categories
docker-compose exec fastapi pytest tests/test_upload_with_ocr.py  # OCR & Upload tests
docker-compose exec fastapi pytest tests/test_db.py              # Database tests
docker-compose exec fastapi pytest tests/test_imports.py         # Import tests
```

### Test Files
- **`test_upload_with_ocr.py`**: Comprehensive upload endpoint testing with real OCR
- **`test_db.py`**: Database functionality and model tests  
- **`test_imports.py`**: Basic import verification

### OCR Test Coverage
Tests include memory-efficient processing of different PDF formats:
- ✅ `bank-statement-1.pdf` (2 pages) - Previously problematic, now working
- ✅ `bank-statement-2.pdf` (1 page) - Standard processing
- ✅ Error scenarios (corrupted files, invalid formats)
- ✅ Memory efficiency (large PDFs without crashes)

## 📊 API Endpoints

### Implemented
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| GET | `/` | Root endpoint | ✅ Working |
| GET | `/health` | Health check | ✅ Working |
| POST | `/upload/statement?client_id={id}` | Upload PDF statement with OCR processing | ✅ Working |
| POST | `/chat` | Chat interface for querying statements with NL-to-SQL | ✅ Working |

### Planned
| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| POST | `/auth/login` | User authentication | ⏳ Planned |
| GET | `/download/csv/{id}` | Download CSV export | ⏳ Planned |
| GET | `/history/sessions` | List chat sessions | ⏳ Planned |

## 🔒 Security Features

- Non-root user in Docker containers
- JWT-based authentication (planned)
- Input validation and sanitization
- Secure file upload handling
- Database connection pooling

## 🚧 Development Status

Current status:

- ✅ Docker containerization
- ✅ Database setup and models
- ✅ FastAPI application foundation
- ✅ File upload endpoints
- ✅ OCR processing pipeline (PaddleOCR with memory-efficient processing)
- ✅ Comprehensive test suite
- ⏳ Chat interface
- ⏳ Authentication system

## 📝 License

Proprietary license - All rights reserved.

---

**Note**: This application is designed for demo purposes and requires additional security hardening for production use. 