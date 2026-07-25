# Prompt para Codex GPT-5.5: Erro 400 Estruturado para Entradas Inválidas na API de Apostas

Você é um engenheiro de software sênior especializado em Python 3.12, FastAPI, Clean Architecture, SOLID, testes automatizados e contratos de API.

A sua missão é evoluir o projeto **LotoBot** para que erros `400` causados por parâmetros ou campos inválidos em `GET /api/v1/bets`, `GET /api/v1/history/bets` e `POST /api/v1/bets/run` retornem detalhes estruturados por campo, em vez da lista textual atual em `error.messages` ou do erro genérico de validação automática com `error.fields`.

Antes de alterar qualquer arquivo, leia o código atual, os testes, `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md` e `pyproject.toml`. Preserve mudanças locais do usuário e adapte a implementação ao estado real do repositório.

Toda lógica interna do código deve continuar em inglês, incluindo nomes de classes, funções, métodos, módulos, variáveis e objetos de domínio. Comentários no código, mensagens de erro, logs personalizados, documentação técnica, README e textos direcionados ao usuário ou mantenedor devem estar em português do Brasil.

## Contexto Atual

O endpoint já existe:

```http
GET /api/v1/bets
```

Atualmente, quando todos os filtros recebem valores inválidos, por exemplo:

```powershell
curl "http://localhost:8000/api/v1/bets?bet_type=abc&lottery_modality=abc&draw_type=abc&month_year=abc&status=abc&sort_by=abc"
```

a API retorna `400` neste formato:

```json
{
  "error": {
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "messages": [
      "Parâmetro bet_type inválido. Valores permitidos: all, individual, pool.",
      "Parâmetro lottery_modality inválido. Valores permitidos: all, MEGA_SENA, QUINA, QUINA_ESPECIAL, LOTECA, LOTECA_ESPECIAL, LOTOFACIL, LOTOFACIL_ESPECIAL, MAIS_MILIONARIA, LOTOMANIA, TIMEMANIA, DUPLA_SENA, DIA_DE_SORTE, SUPER_SETE.",
      "Parâmetro draw_type inválido. Valores permitidos: all, normal, special.",
      "Parâmetro month_year inválido. Use YYYY-MM ou um período relativo permitido.",
      "Parâmetro status inválido. Valores permitidos: all, paid, expired.",
      "Parâmetro sort_by inválido. Valores permitidos: date-asc, date-desc."
    ]
  }
}
```

Esse comportamento está ligado principalmente a:

- `src/application/use_cases/list_portal_bets.py`
- `src/application/exceptions.py`
- `src/application/services/portal_bet_filter_catalog.py`
- `src/api/routes/bets.py`
- `src/api/exceptions.py`
- `src/api/exception_handlers.py`
- `src/api/schemas/error_schema.py`
- `tests/unit/test_portal_bet_validation.py`
- `tests/integration/test_api_portal_bet_validation.py`

Para o endpoint de histórico:

```http
GET /api/v1/history/bets
```

o comportamento atual com query parameters inválidos como:

```powershell
curl "http://localhost:8000/api/v1/history/bets?lottery_modality=abc&draw_number=abc&start_date=abc&end_date=abc"
```

pode retornar apenas o erro automático de datas inválidas:

```json
{
  "error": {
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Corpo da requisição inválido.",
    "fields": [
      "query.end_date",
      "query.start_date"
    ]
  }
}
```

Esse comportamento também deve ser substituído por validação acumulada e estruturada para os filtros de histórico.

Para o endpoint de execução de aposta:

```http
POST /api/v1/bets/run
```

o comportamento atual com corpo inválido como:

```powershell
curl -X 'POST' 'http://localhost:8000/api/v1/bets/run' -H 'accept: application/json; charset=utf-8' -H 'Content-Type: application/json' -d '{"selected_lottery_modality": "abc"}'
```

retorna o erro automático:

```json
{
  "error": {
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Corpo da requisição inválido.",
    "fields": [
      "selected_lottery_modality"
    ]
  }
}
```

Esse comportamento deve ser substituído por erro estruturado com `details`.

## Objetivo

Quando `GET /api/v1/bets` receber parâmetros inválidos, a resposta `400` deve obedecer ao novo contrato:

```json
{
  "error": {
    "timestamp": "2026-06-16T10:00:00-03:00",
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Parâmetros inválidos",
    "details": [
      {
        "field": "bet_type",
        "rejected_value": "abc",
        "allowed_values": [
          "all",
          "individual",
          "pool"
        ],
        "message": "Valor inválido."
      },
      {
        "field": "lottery_modality",
        "rejected_value": "abc",
        "allowed_values": [
          "all",
          "MEGA_SENA",
          "QUINA",
          "QUINA_ESPECIAL",
          "LOTECA",
          "LOTECA_ESPECIAL",
          "LOTOFACIL",
          "LOTOFACIL_ESPECIAL",
          "MAIS_MILIONARIA",
          "LOTOMANIA",
          "TIMEMANIA",
          "DUPLA_SENA",
          "DIA_DE_SORTE",
          "SUPER_SETE"
        ],
        "message": "Valor inválido."
      },
      {
        "field": "draw_type",
        "rejected_value": "abc",
        "allowed_values": [
          "all",
          "normal",
          "special"
        ],
        "message": "Valor inválido."
      },
      {
        "field": "month_year",
        "rejected_value": "abc",
        "message": "Valor inválido. Utilize o formato YYYY-MM ou um período relativo válido."
      },
      {
        "field": "status",
        "rejected_value": "abc",
        "allowed_values": [
          "all",
          "paid",
          "expired"
        ],
        "message": "Valor inválido."
      },
      {
        "field": "sort_by",
        "rejected_value": "abc",
        "allowed_values": [
          "date-asc",
          "date-desc"
        ],
        "message": "Valor inválido."
      }
    ]
  }
}
```

O valor de `timestamp` acima é apenas exemplo. Em execução real, gere o timestamp no momento da resposta, com timezone `America/Sao_Paulo`, formato ISO 8601, offset `-03:00` quando aplicável e sem microssegundos.

## Objetivo para `GET /api/v1/history/bets`

Quando `GET /api/v1/history/bets` receber parâmetros inválidos, a resposta `400` também deve obedecer ao contrato estruturado:

```json
{
  "error": {
    "timestamp": "2026-06-16T10:00:00-03:00",
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Parâmetros inválidos",
    "details": [
      {
        "field": "lottery_modality",
        "rejected_value": "abc",
        "allowed_values": [
          "all",
          "MEGA_SENA",
          "QUINA",
          "QUINA_ESPECIAL",
          "LOTECA",
          "LOTECA_ESPECIAL",
          "LOTOFACIL",
          "LOTOFACIL_ESPECIAL",
          "MAIS_MILIONARIA",
          "LOTOMANIA",
          "TIMEMANIA",
          "DUPLA_SENA",
          "DIA_DE_SORTE",
          "SUPER_SETE"
        ],
        "message": "Valor inválido."
      },
      {
        "field": "draw_number",
        "rejected_value": "abc",
        "message": "Valor inválido. Informe número maior que zero."
      },
      {
        "field": "start_date",
        "rejected_value": "abc",
        "message": "Valor inválido. Utilize o formato YYYY-MM-DD."
      },
      {
        "field": "end_date",
        "rejected_value": "abc",
        "message": "Valor inválido. Utilize o formato YYYY-MM-DD."
      }
    ]
  }
}
```

## Objetivo para `POST /api/v1/bets/run`

Quando `POST /api/v1/bets/run` receber `selected_lottery_modality` inválido, a resposta `400` deve obedecer ao contrato estruturado:

```json
{
  "error": {
    "timestamp": "2026-06-16T10:00:00-03:00",
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Campos inválidos",
    "details": [
      {
        "field": "selected_lottery_modality",
        "rejected_value": "abc",
        "allowed_values": [
          "all",
          "MEGA_SENA",
          "QUINA",
          "QUINA_ESPECIAL",
          "LOTECA",
          "LOTECA_ESPECIAL",
          "LOTOFACIL",
          "LOTOFACIL_ESPECIAL",
          "MAIS_MILIONARIA",
          "LOTOMANIA",
          "TIMEMANIA",
          "DUPLA_SENA",
          "DIA_DE_SORTE",
          "SUPER_SETE"
        ],
        "message": "Valor inválido."
      }
    ]
  }
}
```

Referente ao campo `selected_lottery_modality` do endpoint `/api/v1/bets/run`, siga a mesma lógica de validação do parâmetro `lottery_modality` do endpoint `/api/v1/bets`, incluindo a lista de `allowed_values` definida neste prompt.

## Regras de Implementação

- A mudança deve afetar especificamente erros de validação acumulada dos filtros de `GET /api/v1/bets` e `GET /api/v1/history/bets`, além do campo `selected_lottery_modality` em `POST /api/v1/bets/run`.
- Preserve os demais contratos de erro já existentes, exceto se for necessário ampliar tipos/schemas de forma retrocompatível.
- Substitua, para esse caso, `error.messages` por:
  - `error.timestamp`
  - `error.message`: `"Parâmetros inválidos"`
  - `error.details`: lista estruturada por parâmetro inválido.
- Preserve `error.status_code = 400`.
- Preserve `error.code = "REQUISICAO_INVALIDA"`.
- A validação deve continuar acumulando todos os parâmetros inválidos antes de retornar erro.
- Valores inválidos devem continuar retornando `400` antes de qualquer interação com Playwright.
- Não transforme esse caso em validação automática do FastAPI/Pydantic que interrompa no primeiro erro.
- Não acople `application` a FastAPI, Starlette ou schemas HTTP.
- Não acople `domain` ou `application` a `api`.
- Não adicione dependência de Playwright na camada `api`.
- Não altere o significado de `/api/v1/history/bets`.
- Não altere o comportamento de `POST /api/v1/bets/run`.
- Em `/api/v1/history/bets`, não permita que `start_date=abc` ou `end_date=abc` sejam tratados apenas pelo erro automático genérico de `RequestValidationError`; esses parâmetros devem entrar no mesmo envelope estruturado com `details`.
- Em `/api/v1/bets/run`, não permita que `selected_lottery_modality=abc` seja tratado apenas pelo erro automático genérico de `RequestValidationError`; esse campo deve entrar no envelope estruturado com `details`.
- Caso possível, evite lógica duplicada. Centralize validações, listas de valores permitidos, montagem de `details` e geração do envelope estruturado em componentes reutilizáveis, respeitando as fronteiras da Clean Architecture.
- Após os ajustes, remova os atributos `fields` e `messages` da classe `ApiError`. O contrato interno de erro deve usar `message` e, quando aplicável, `details`.
- Remova dependências residuais de `error.fields` e `error.messages` nos handlers, schemas, testes e documentação, exceto se houver compatibilidade explicitamente necessária fora do escopo. Para os três casos deste prompt, `fields` e `messages` não devem ser retornados.

## Modelo de Detalhe de Erro

Crie ou adapte um objeto interno para representar detalhes de validação de filtros, preferencialmente na camada `application`, sem dependência de framework HTTP.

Cada detalhe deve carregar:

- `field`: nome do query parameter.
- `rejected_value`: valor original recebido na requisição, sem normalização.
- `allowed_values`: lista de valores permitidos, quando aplicável.
- `message`: mensagem curta em português.

Para `month_year`, não retorne `allowed_values` no caso de formato inválido `abc`. Retorne:

```json
{
  "field": "month_year",
  "rejected_value": "abc",
  "message": "Valor inválido. Utilize o formato YYYY-MM ou um período relativo válido."
}
```

Se `month_year` estiver em formato válido mas fora da janela permitida, mantenha a resposta estruturada, mas nesse caso é aceitável retornar `allowed_values` com os meses permitidos calculados dinamicamente.

## Valores Permitidos

Use exatamente estas listas e esta ordem no contrato de erro:

### `bet_type`

```json
["all", "individual", "pool"]
```

### `lottery_modality`

```json
[
  "all",
  "MEGA_SENA",
  "QUINA",
  "QUINA_ESPECIAL",
  "LOTECA",
  "LOTECA_ESPECIAL",
  "LOTOFACIL",
  "LOTOFACIL_ESPECIAL",
  "MAIS_MILIONARIA",
  "LOTOMANIA",
  "TIMEMANIA",
  "DUPLA_SENA",
  "DIA_DE_SORTE",
  "SUPER_SETE"
]
```

### `draw_type`

```json
["all", "normal", "special"]
```

### `status`

```json
["all", "paid", "expired"]
```

### `sort_by`

```json
["date-asc", "date-desc"]
```

### `draw_number` em `/api/v1/history/bets`

O parâmetro `draw_number` deve ser tratado como inteiro positivo.

- Altere o tipo semântico do parâmetro para `int`.
- Aceite apenas números inteiros maiores que zero.
- Quando inválido, retorne detalhe sem `allowed_values`:

```json
{
  "field": "draw_number",
  "rejected_value": "abc",
  "message": "Valor inválido. Informe número maior que zero."
}
```

### `start_date` e `end_date` em `/api/v1/history/bets`

Os parâmetros `start_date` e `end_date` devem aceitar datas no formato `YYYY-MM-DD`.

- Não use `datetime` diretamente na assinatura FastAPI para esses parâmetros se isso impedir validação acumulada.
- Receba os valores brutos como `str | None`, valide manualmente e converta para o tipo interno adequado depois da validação.
- Quando inválidos, retorne detalhe sem `allowed_values`:

```json
{
  "field": "start_date",
  "rejected_value": "abc",
  "message": "Valor inválido. Utilize o formato YYYY-MM-DD."
}
```

### `selected_lottery_modality` em `/api/v1/bets/run`

O campo `selected_lottery_modality` deve seguir a mesma regra de `lottery_modality` de `/api/v1/bets`.

- Valide contra a lista pública de modalidades definida neste prompt.
- Preserve o valor original inválido em `rejected_value`.
- Quando inválido, retorne:

```json
{
  "field": "selected_lottery_modality",
  "rejected_value": "abc",
  "allowed_values": [
    "all",
    "MEGA_SENA",
    "QUINA",
    "QUINA_ESPECIAL",
    "LOTECA",
    "LOTECA_ESPECIAL",
    "LOTOFACIL",
    "LOTOFACIL_ESPECIAL",
    "MAIS_MILIONARIA",
    "LOTOMANIA",
    "TIMEMANIA",
    "DUPLA_SENA",
    "DIA_DE_SORTE",
    "SUPER_SETE"
  ],
  "message": "Valor inválido."
}
```

```json
{
  "field": "end_date",
  "rejected_value": "abc",
  "message": "Valor inválido. Utilize o formato YYYY-MM-DD."
}
```

## Ajustes Esperados no Código

### Camada `application`

- Evolua `PortalBetFiltersValidationError` para transportar detalhes estruturados, não apenas mensagens textuais.
- Ajuste `ListPortalBetsUseCase` para acumular detalhes por campo.
- Preserve a ordem de validação:
  1. `bet_type`
  2. `lottery_modality`
  3. `draw_type`
  4. `month_year`
  5. `status`
  6. `sort_by`
- Preserve o valor rejeitado original recebido no `run`.
- Centralize as listas permitidas para evitar duplicação entre parser, rota, erro e testes.
- Se necessário, adapte `portal_bet_filter_catalog.py` para expor metadados de validação de forma reutilizável.
- Crie ou adapte uma validação equivalente para os filtros de histórico, preferencialmente reutilizando o mesmo modelo de detalhe estruturado.
- Em `ListPlacedBetsUseCase`, altere o contrato de entrada para trabalhar com `LotteryModality | None` já validado para `lottery_modality` e `int | None` para `draw_number`, ou centralize a conversão em uma função de aplicação sem dependência de FastAPI.
- Preserve o DTO `BetSearchFilters` e a porta `BetRepositoryPort` coerentes com o novo tipo semântico de `draw_number`. Se o modelo persistido armazenar concurso como string, converta no adapter/repositório ou no ponto de fronteira apropriado sem quebrar a API pública.
- A validação de `lottery_modality` em `/api/v1/history/bets` deve seguir a mesma lógica de `lottery_modality` de `/api/v1/bets`, incluindo `allowed_values` com `all` e os nomes de `LotteryModality` na ordem definida neste prompt.
- A validação de `selected_lottery_modality` em `/api/v1/bets/run` deve reutilizar a mesma fonte de verdade da validação de `lottery_modality`, evitando listas duplicadas em schema, rota, caso de uso e testes.

### Camada `api`

- Ajuste `ApiError` e `api_error_handler` para suportar `details` quando fornecido.
- Remova `fields` e `messages` de `ApiError` depois de migrar os usos para `details`.
- Ajuste `api_error_handler`, `request_validation_error_handler` e `_error_response` para não dependerem de atributos removidos.
- Inclua `timestamp` apenas no envelope do erro estruturado de parâmetros inválidos, ou de forma segura em envelopes que passarem a exigir esse campo. Não quebre testes/contratos de erros não relacionados sem necessidade.
- Gere o timestamp no handler ou no ponto mais centralizado possível usando timezone de São Paulo.
- Ajuste `_raise_bad_request_messages` em `src/api/routes/bets.py` ou substitua por uma função específica, por exemplo `_raise_bad_request_details`.
- Atualize `src/api/schemas/error_schema.py` para documentar `timestamp` e `details`.
- Atualize exemplos OpenAPI de `400` para `GET /api/v1/bets` e `GET /api/v1/history/bets` com o novo contrato.
- Em `/api/v1/history/bets`, altere a assinatura da rota para evitar interrupção prematura do FastAPI nos campos que precisam de validação acumulada. Uma abordagem aceitável é receber os query parameters como `str | None`, validar manualmente e só depois converter para `LotteryModality`, `int` e datas.
- Referente ao endpoint `/api/v1/history/bets`, altere o tipo do parâmetro `lottery_modality` para `LotteryModality` no contrato interno validado.
- Referente ao endpoint `/api/v1/history/bets`, altere o tipo do parâmetro `draw_number` para `int` no contrato interno validado.
- Em `POST /api/v1/bets/run`, evite que o schema Pydantic interrompa a requisição antes de a API conseguir preservar `rejected_value`. Uma abordagem aceitável é receber o campo bruto, validar manualmente e converter para `LotteryModality` apenas depois da validação estruturada.
- Atualize `BetRunRequest` e seus testes conforme necessário para preservar o OpenAPI e permitir o novo contrato de erro.
- Referente às classes `PortalBetResponse` e `PlacedBetResponse` em `src/api/schemas/automation_schema.py`, altere o tipo do atributo `lottery_modality` para `LotteryModality`.
- Ajuste os mappers das rotas para preencherem `PortalBetResponse.lottery_modality` e `PlacedBetResponse.lottery_modality` com `LotteryModality`, não `str`.
- Atualize os exemplos dos schemas, OpenAPI e testes para refletirem a serialização esperada de `LotteryModality`, mantendo o contrato público consistente com os demais endpoints.

## Testes Obrigatórios

Atualize ou crie testes cobrindo:

- `ListPortalBetsUseCase` acumula todos os detalhes estruturados de validação.
- O adapter/porta do portal não é chamado quando há parâmetros inválidos.
- O valor rejeitado original é preservado em `rejected_value`.
- A ordem dos detalhes segue a ordem dos parâmetros.
- `GET /api/v1/bets?bet_type=abc&lottery_modality=abc&draw_type=abc&month_year=abc&status=abc&sort_by=abc` retorna `400` com:
  - `error.timestamp` presente em ISO 8601 com timezone.
  - `error.status_code = 400`.
  - `error.code = "REQUISICAO_INVALIDA"`.
  - `error.message = "Parâmetros inválidos"`.
  - `error.details` exatamente com os campos e valores permitidos definidos neste prompt.
  - ausência de `error.messages`.
- `month_year=abc` não retorna `allowed_values`.
- Um `month_year` fora da janela permitida continua retornando erro `400` estruturado.
- `GET /api/v1/history/bets?lottery_modality=abc&draw_number=abc&start_date=abc&end_date=abc` retorna `400` com:
  - `error.timestamp` presente em ISO 8601 com timezone.
  - `error.status_code = 400`.
  - `error.code = "REQUISICAO_INVALIDA"`.
  - `error.message = "Parâmetros inválidos"`.
  - `error.details` exatamente com `lottery_modality`, `draw_number`, `start_date` e `end_date`.
  - ausência de `error.fields`.
  - ausência de `error.messages`.
- `lottery_modality=abc` em `/api/v1/history/bets` retorna a mesma lista `allowed_values` usada em `/api/v1/bets`.
- `draw_number=abc`, `draw_number=0` e `draw_number=-1` em `/api/v1/history/bets` retornam erro estruturado com a mensagem `"Valor inválido. Informe número maior que zero."`.
- `start_date=abc` e `end_date=abc` em `/api/v1/history/bets` retornam erro estruturado com a mensagem `"Valor inválido. Utilize o formato YYYY-MM-DD."`.
- `start_date` maior que `end_date` continua retornando `400`; se possível, use o mesmo envelope estruturado com detalhe apropriado para o campo ou período.
- `POST /api/v1/bets/run` com `{"selected_lottery_modality": "abc"}` retorna `400` com:
  - `error.timestamp` presente em ISO 8601 com timezone.
  - `error.status_code = 400`.
  - `error.code = "REQUISICAO_INVALIDA"`.
  - `error.message = "Campos inválidos"`.
  - `error.details` contendo somente `selected_lottery_modality`.
  - `allowed_values` na mesma ordem definida neste prompt.
  - ausência de `error.fields`.
  - ausência de `error.messages`.
- `ApiError` não possui mais atributos `fields` nem `messages`, e os testes devem garantir que os fluxos migrados usam `details`.
- Erros não relacionados, como sessão fechada `409`, continuam no contrato esperado.
- `/api/v1/history/bets` e `/api/v1/history/bets/{bet_id}` continuam funcionais.
- `POST /api/v1/bets/run` continua funcional.
- O OpenAPI documenta o novo erro estruturado de validação.
- As regras de arquitetura continuam passando.
- A cobertura configurada em `pyproject.toml` continua em 100%.

Use relógio/fake determinístico nos testes sempre que validar timestamp ou janela de mês. Para teste de timestamp gerado pelo handler, valide o formato e o timezone sem depender de segundo exato, ou injete/monkeypatch o fornecedor de tempo se já houver padrão no projeto.

## Documentação

Atualize `README.md` na seção de respostas de erro e na documentação de `GET /api/v1/bets`, `GET /api/v1/history/bets` e `POST /api/v1/bets/run`, incluindo exemplos do novo envelope `400` para filtros ou campos inválidos.

Atualize `ARCHITECTURE.md` ou `DEVELOPMENT.md` apenas se a solução introduzir uma nova convenção relevante para erros estruturados de validação.

## Validação Recomendada

Execute:

```powershell
python -m ruff format src tests
python -m ruff check --fix src tests
python -m pytest
python -m pytest --cov=src --cov-report=term-missing
python -m pytest tests/unit/test_architecture.py
```

Depois de qualquer correção automática, execute novamente a suíte completa.

## Critérios de Aceite

A entrega está correta quando:

- O `curl` informado retorna `400` no novo formato com `details`.
- O `curl` de histórico com `lottery_modality=abc&draw_number=abc&start_date=abc&end_date=abc` retorna `400` no novo formato com `details`.
- O `curl` de execução de aposta com `{"selected_lottery_modality": "abc"}` retorna `400` no novo formato com `message: "Campos inválidos"` e `details`.
- `error.messages` não aparece nesse erro de parâmetros inválidos.
- `error.fields` não aparece nos erros estruturados de parâmetros ou campos inválidos desses fluxos.
- Cada detalhe contém `field`, `rejected_value`, `message` e `allowed_values` quando aplicável.
- `month_year=abc` retorna a mensagem específica sem `allowed_values`.
- `start_date=abc` e `end_date=abc` retornam mensagem específica de formato `YYYY-MM-DD`.
- `draw_number` em `/api/v1/history/bets` é validado como inteiro maior que zero e tratado internamente como `int`.
- `lottery_modality` em `/api/v1/history/bets` segue a mesma lógica de validação de `lottery_modality` em `/api/v1/bets`.
- `selected_lottery_modality` em `/api/v1/bets/run` segue a mesma lógica de validação de `lottery_modality` em `/api/v1/bets`.
- A classe `ApiError` não expõe mais os atributos `fields` e `messages`.
- `PortalBetResponse.lottery_modality` e `PlacedBetResponse.lottery_modality` são tipados como `LotteryModality`.
- Todos os filtros inválidos são reportados em uma única resposta.
- A resposta inclui `timestamp` com timezone de São Paulo.
- O erro é produzido antes de qualquer chamada ao portal.
- Os contratos não relacionados permanecem estáveis.
- A documentação reflete o novo comportamento.
- A suíte completa, arquitetura e cobertura passam.
