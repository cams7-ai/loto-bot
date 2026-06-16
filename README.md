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

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Configuração

Copie `.env.example` para `.env` e preencha apenas localmente. Nunca versionar CPF, senha, CVV, cartão ou códigos reais.

`CONFIRMA_PAGAMENTO=false` é o padrão seguro. O clique real de confirmação de pagamento só é executado quando `CONFIRMA_PAGAMENTO=true`.

As variáveis `LOTTOBOT_BROWSER_PROFILE_DIR`, `LOTTOBOT_BROWSER_HEADLESS` e `LOTTOBOT_BROWSER_TIMEOUT_SECONDS` controlam o Chromium do Playwright. O diretório de perfil persistente é criado automaticamente e caminhos relativos são resolvidos a partir da raiz local do projeto, seguindo o mesmo comportamento usado no `whatsapp-notify`.

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

Os testes usam fakes e `httpx.MockTransport`. Nenhum teste abre o Chromium nem acessa `URL_LOTERIAS_ONLINE`.

## Integrações Locais

- Gmail Reader: `GET /api/v1/validation-code`
- Mail Sender: `POST /api/v1/mail/send`
- WhatsApp Notify: endpoints `/whatsapp/session/*` e `/whatsapp/messages/send`

Falhas operacionais tentam notificar pelo WhatsApp Web e usam e-mail como fallback.
