# Contributing to Hermes V2

Thank you for your interest in contributing! This document outlines how to get started.

## Development Setup

1. **Clone and configure:**
   ```bash
   git clone https://github.com/yourusername/hermes-v2.git
   cd hermes-v2
   cp .env.example .env
   # Add your OPENROUTER_API_KEY to .env
   ```

2. **Start services:**
   ```bash
   docker compose up -d
   ```

3. **Run tests:**
   ```bash
   docker exec hermes_backend python3 -m pytest tests/ -v
   ```

## Code Style

- **Language**: Python 3.12+
- **Formatting**: Ruff
- **Type hints**: Required for all functions
- **Docstrings**: Google style
- **Tests**: pytest, with async support via pytest-asyncio

## Project Structure

- `backend/api/` — FastAPI routes and middleware
- `backend/core/` — Core infrastructure (config, DB, LLM gateway)
- `backend/domain/` — Business logic modules
- `backend/tests/` — Test suites
- `frontend/` — React frontend
- `docs/` — Documentation
- `scripts/` — Utility scripts

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes and add tests
4. Ensure all tests pass (`docker exec hermes_backend python3 -m pytest tests/ -q`)
5. Commit with clear messages (`git commit -m "feat: add amazing feature"`)
6. Push and open a Pull Request

## Commit Convention

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation
- `test:` — Tests
- `refactor:` — Code refactoring
- `chore:` — Maintenance

## Testing Guidelines

- Write tests for all new features
- Use `pytest-asyncio` for async tests
- Mock external services (LLM, DB) in unit tests
- Integration tests go in `tests/test_*.py`
- Bug regression tests go in `tests/test_audit.py`

## Questions?

Open an issue or check the `docs/` folder for detailed documentation.
