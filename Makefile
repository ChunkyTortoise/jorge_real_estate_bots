.PHONY: demo test health lint clean quickstart-client

demo:
	python jorge_launcher.py --demo

test:
	pytest -v --tb=short

health:
	@echo "Checking bot health..."
	@curl -sf http://localhost:8001/health 2>/dev/null && echo "Lead Bot:   OK" || echo "Lead Bot:   DOWN"
	@curl -sf http://localhost:8002/health 2>/dev/null && echo "Seller Bot: OK" || echo "Seller Bot: DOWN"
	@curl -sf http://localhost:8003/health 2>/dev/null && echo "Buyer Bot:  OK" || echo "Buyer Bot:  DOWN"

lint:
	ruff check .
	ruff format --check .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .demo_data

quickstart-client:
	@echo "Quickstart checklist for new client deployment"
	@echo "1) cp .env.example .env"
	@echo "2) Set ANTHROPIC_API_KEY, GHL_API_KEY, GHL_LOCATION_ID, DATABASE_URL, REDIS_URL"
	@echo "3) docker compose up -d postgres redis"
	@echo "4) python jorge_launcher.py --demo"
	@echo "5) Call POST /api/onboarding/validate-credentials and POST /api/onboarding/bootstrap"
