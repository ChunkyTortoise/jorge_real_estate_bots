.PHONY: demo test health lint clean

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
