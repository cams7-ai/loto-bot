# LotoBot

LotoBot é uma API REST em Python 3.12 para controlar uma sessão persistente do Chromium e executar, de forma observável e protegida, o fluxo de aposta no portal Loterias Online CAIXA.

O código segue Clean Architecture: domínio e casos de uso não dependem de FastAPI, Playwright, HTTP, PyMongo ou Beanie. Integrações externas ficam em adapters de infraestrutura e podem ser substituídas por fakes nos testes.

## Recursos

- `GET /health`: verifica a disponibilidade da API.
- `GET /api/v1/sessions/start`: inicia a sessão do navegador e tenta iniciar o WhatsApp Web.
- `GET /api/v1/sessions/stop`: encerra o navegador e o WhatsApp Web.
- `GET /api/v1/sessions/status`: consulta o estado da sessão.
- `GET /api/v1/bets/run`: executa o fluxo principal de aposta.
- `GET /api/v1/history/bets`: lista apostas persistidas no MongoDB, com filtros opcionais.
- `GET /api/v1/history/bets/{bet_id}`: consulta uma aposta persistida pelo identificador.
- Swagger UI em `/docs`, ReDoc em `/redoc` e OpenAPI em `/openapi.json`.

## Arquitetura

O projeto separa responsabilidades em quatro camadas principais:

- `domain`: entidades, enums, value objects, constantes e exceções de domínio.
- `application`: casos de uso, portas, DTOs, serviços de aplicação e montagem de mensagens operacionais.
- `infrastructure`: adapters concretos para Playwright, clients HTTP, configuração, logging, seletores e banco.
- `api`: rotas FastAPI, schemas, handlers HTTP, mappers e composição de dependências.

As regras de dependência são validadas por testes de arquitetura com `grimp`:

- `domain` não pode depender de `application`, `api` ou `infrastructure`.
- `application` não pode depender de `api` ou `infrastructure`.
- `infrastructure` não pode depender de `api`.
- `api` não pode acessar diretamente Playwright, PyMongo, Beanie ou clients HTTP.
- Frameworks externos proibidos por camada também são checados nos testes.

Para executar apenas os testes de arquitetura:

```powershell
python -m pytest tests/unit/test_architecture.py
```

## Exemplos da API

### Saúde

```powershell
curl http://localhost:8000/health
```

Resposta:

```json
{
  "status": "ok",
  "application": "LotoBot"
}
```

### Executar Fluxo de Aposta

```powershell
curl http://localhost:8000/api/v1/bets/run
```

Resposta:

```json
{
  "session_id": "00000000-0000-0000-0000-000000000001",
  "status": "finished",
  "message": "Aposta finalizada com sucesso.",
  "executed_operation": "Completa a aposta",
  "purchase_number": "123456"
}
```

### Listar Histórico de Apostas

```powershell
curl "http://localhost:8000/api/v1/history/bets"
```

Resposta:

```json
[
  {
    "bet_id": "64ef8f7a6f9a8f0f8f0f8f0f",
    "lottery_modality": "mega-sena",
    "selected_numbers": ["01", "02", "03", "04", "05", "06"],
    "draw_number": "1234",
    "status": "Efetivada",
    "bet_amount": "5.00",
    "purchase_number": "123456",
    "bet_date": "2026-07-12T18:08:14"
  }
]
```

Filtros opcionais:

```powershell
curl "http://localhost:8000/api/v1/history/bets?lottery_modality=mega-sena&draw_number=1234&start_date=2026-07-01T00:00:00&end_date=2026-07-31T23:59:59"
```

Parâmetros aceitos:

- `lottery_modality`: modalidade da loteria, por exemplo `mega-sena`.
- `draw_number`: número do concurso.
- `start_date`: início do intervalo de `bet_date`.
- `end_date`: fim do intervalo de `bet_date`.

### Consultar Aposta por Identificador

```powershell
curl http://localhost:8000/api/v1/history/bets/64ef8f7a6f9a8f0f8f0f8f0f
```

Resposta:

```json
{
  "bet_id": "64ef8f7a6f9a8f0f8f0f8f0f",
  "lottery_modality": "mega-sena",
  "selected_numbers": ["01", "02", "03", "04", "05", "06"],
  "draw_number": "1234",
  "status": "Efetivada",
  "bet_amount": "5.00",
  "purchase_number": "123456",
  "bet_date": "2026-07-12T18:08:14"
}
```

Quando o identificador for inválido, a API retorna `400`. Quando a aposta não existir, a API retorna `404`.

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
- `404`: `ROTA_NAO_ENCONTRADA`.
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

Copie `.env.example` para `.env` e preencha apenas localmente. Nunca versione CPF, senha, CVV, dados de cartão, tokens ou códigos reais.

`CONFIRM_PAYMENT=false` é o padrão seguro. O clique real de confirmação de pagamento só é executado quando `CONFIRM_PAYMENT=true`.

`MONGODB_ENABLED=false` também é o padrão seguro. Com esse valor, o fluxo local comum não exige MongoDB. Para persistir e consultar apostas finalizadas, configure:

```env
MONGODB_ENABLED=true
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=loto_bot
```

As variáveis `BROWSER_PROFILE_DIR`, `BROWSER_HEADLESS` e `BROWSER_TIMEOUT_SECONDS` controlam o Chromium do Playwright. O diretório de perfil persistente é criado automaticamente e caminhos relativos são resolvidos a partir da raiz local do projeto.

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

Além dos testes unitários e de integração, a suíte inclui testes de arquitetura com `grimp` para impedir dependências indevidas entre camadas.

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
