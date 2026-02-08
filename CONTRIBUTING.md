# Contributing

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Clone and install
git clone https://github.com/ChunkyTortoise/jorge_real_estate_bots.git
cd jorge_real_estate_bots
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
make test

# Run linter
make lint
```

## Workflow

1. Fork the repository and create a feature branch (`git checkout -b feature/your-feature`)
2. Write tests for your changes
3. Ensure all tests pass (`make test`)
4. Ensure code passes lint (`make lint`)
5. Commit with a clear message following conventional commits
6. Open a Pull Request

## Code Style

- Follow PEP 8, enforced by `ruff`
- Use type hints for function signatures
- Add docstrings to public functions and classes
- Keep functions focused and under 50 lines

## Testing

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use descriptive test names that explain expected behavior
- Run the full suite before submitting: `make test`

## Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Update documentation if needed
- Reference related issues in the PR description

## Questions?

Open an issue with the "question" label or check existing issues and discussions.
