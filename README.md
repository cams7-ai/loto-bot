# LotoBot

LotoBot é uma API REST em Python 3.12 para controlar uma sessão persistente do Chromium e executar, de forma observável e protegida, o fluxo de aposta no portal Loterias Online CAIXA.

O código segue Clean Architecture: domínio e casos de uso não dependem de FastAPI, Playwright ou HTTP. Integrações externas ficam em adapters de infraestrutura e podem ser substituídas por fakes nos testes.

## Recursos

- `GET /health`: disponibilidade da API.
- `GET /api/v1/sessions/start`: inicia sessão de navegador e tenta iniciar o WhatsApp Web.
- `GET /api/v1/sessions/stop`: encerra navegador e WhatsApp Web.
- `GET /api/v1/sessions/status`: consulta estado da sessão.
- `GET /api/v1/bets/run`: executa o fluxo principal de aposta.
- Swagger UI em `/docs`, ReDoc em `/redoc` e OpenAPI em `/openapi.json`.

## Respostas de Erro

As exceções de domínio carregam o `status_code` como `http.HTTPStatus`. O `ApiExceptionMapper` usa esse valor para transformar falhas de automação em respostas HTTP padronizadas.

O corpo de erro segue o formato:

```json
{
  "error": {
    "status_code": 409,
    "code": "SESSAO_FECHADA",
    "message": "A sessão de navegador já está fechada"
  }
}
```

Quando houver erro de validação de entrada, o campo `fields` pode ser retornado:

```json
{
  "error": {
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Corpo da requisição inválido.",
    "fields": ["cpf"]
  }
}
```

O OpenAPI documenta exemplos específicos por código de erro em cada status HTTP, incluindo:

- `400`: `REQUISICAO_INVALIDA`, `CPF_INVALIDO`.
- `403`: `CONFIRMACAO_PAGAMENTO_DESABILITADA`.
- `409`: `SESSAO_JA_ABERTA`, `SESSAO_FECHADA`, `REGISTRO_APOSTA_INDIVIDUAL_FECHADO`, `APOSTA_TEMPORARIAMENTE_DESABILITADA`.
- `429`: `LIMITE_MAXIMO_DIARIO_DE_COMPRAS`.
- `500`: `FALHA_NA_AUTOMACAO`, `ERRO_INTERNO`.
- `502`: `ERRO_NO_REDIRECIONAMENTO_DA_PAGINA`.
- `503`: `SERVICO_EXTERNO_INDISPONIVEL`.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Configuração

Copie `.env.example` para `.env` e preencha apenas localmente. Nunca versionar CPF, senha, CVV, cartão ou códigos reais.

`CONFIRM_PAYMENT=false` é o padrão seguro. O clique real de confirmação de pagamento só é executado quando `CONFIRM_PAYMENT=true`.

As variáveis `BROWSER_PROFILE_DIR`, `BROWSER_HEADLESS` e `BROWSER_TIMEOUT_SECONDS` controlam o Chromium do Playwright. O diretório de perfil persistente é criado automaticamente e caminhos relativos são resolvidos a partir da raiz local do projeto, seguindo o mesmo comportamento usado no `whatsapp-notify`.

## Execução

```powershell
python -m uvicorn api.server:app --app-dir src --host 0.0.0.0 --port 8000
```

Ou:

```powershell
python src/main.py
```

## Testes

```powershell
python -m pytest
```

Os testes usam fakes e `httpx.MockTransport`. Nenhum teste abre o Chromium nem acessa `ONLINE_LOTTERY_URL`.

## Formatação e Qualidade

O projeto usa Ruff para formatação e correções automáticas de lint.

```powershell
python -m ruff format src tests
python -m ruff check --fix src tests
```

A configuração fica em `pyproject.toml`, com Python alvo `py312`, largura de linha `120` e regras básicas de lint para erros, imports, modernização, bugs comuns e simplificações.

## Integrações Locais

- Gmail Reader: `GET /api/v1/validation-code`
- Mail Sender: `POST /api/v1/mail/send`
- WhatsApp Notify: endpoints `/whatsapp/session/*` e `/whatsapp/messages/send`

Falhas operacionais tentam notificar pelo WhatsApp Web e usam e-mail como fallback.
