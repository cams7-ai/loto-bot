#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
    echo "Uso: $0 <APPLICATION_SECRET_PATH> (ex.: file://application-secret.json)" >&2
    exit 1
fi
DESTINATION=${1#file://}
if [ -z "$DESTINATION" ]; then
    echo "Informe o caminho do arquivo de destino." >&2
    exit 1
fi

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_BIN=python3
fi
exec "$PYTHON_BIN" - "$PROJECT_ROOT" "$DESTINATION" <<'PY'
import json
import os
from pathlib import Path
import sys
import tempfile

try:
    from dotenv import dotenv_values
except ImportError:
    sys.exit("Instale python-dotenv no Python utilizado pelo script (consulte o guia Linux).")

root = Path(sys.argv[1])
source = root / ".env"
if not source.is_file():
    sys.exit(f"Arquivo não encontrado: {source}")
# Leia apenas o arquivo, sem substituir valores por variáveis do ambiente.
environment = dotenv_values(source, interpolate=False)
fields = {
    "BETTOR_CPF": "bettor_cpf",
    "BETTOR_PASSWORD": "bettor_password",
    "CREDIT_CARD_LAST_DIGITS": "credit_card_last_digits",
    "CREDIT_CARD_SECURITY_CODE": "credit_card_security_code",
    "MAIL_TO": "mail_to",
}
missing = [name for name in fields if not environment.get(name)]
if missing:
    sys.exit("Preencha as variáveis obrigatórias no .env: " + ", ".join(missing))

values = {key: environment[name] for name, key in fields.items()}
if any("\n" in value or "\r" in value for value in values.values()):
    sys.exit("As variáveis do segredo não podem conter quebras de linha.")

destination = Path(sys.argv[2]).absolute()
temporary = None
try:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(values, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, destination)
finally:
    if temporary is not None:
        temporary.unlink(missing_ok=True)

print(f"Arquivo criado ou sobrescrito: {destination}")
PY
