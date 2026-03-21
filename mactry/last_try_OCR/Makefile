.PHONY: install dev run run-prod test lint clean reset pull-ollama check-ollama

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

run:
	uvicorn last_try_OCR.server.app:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	uvicorn last_try_OCR.server.app:app \
		--host 0.0.0.0 --port 8000 \
		--workers 1 \
		--loop uvloop \
		--access-log

test:
	pytest tests/ -v --tb=short

lint:
	ruff check . --fix
	ruff format .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete

reset:
	rm -rf last_try_output/
	@echo "Output directory cleared."

pull-ollama:
	ollama pull qwen2.5vl:7b

check-ollama:
	curl -s http://localhost:11434/api/tags | python3 -m json.tool
