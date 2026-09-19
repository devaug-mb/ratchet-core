.PHONY: test lint type check format

# Ejecuta la batería de tests.
test:
	pytest

# Lint (estilo, imports, errores comunes).
lint:
	ruff check src tests

# Comprobación de tipos.
type:
	mypy src

# Todo lo anterior: la comprobación completa antes de dar por buena una iteración.
check: lint type test

# Formatea el código (opcional).
format:
	ruff format src tests
