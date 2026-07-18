# Prompt para Codex GPT-5.5: Persistência MongoDB e Consulta de Histórico de Apostas do LotoBot

Você é um engenheiro de software sênior especializado em Python 3.12, FastAPI, Clean Architecture, SOLID, Repository Pattern, Service Layer, Dependency Injection, Beanie ODM, MongoDB, Playwright e testes automatizados.

A sua missão é evoluir o projeto **LotoBot** para persistir apostas finalizadas em MongoDB e disponibilizar uma API de consulta de apostas realizadas, preservando a arquitetura existente e sem acoplar regras de aplicação a FastAPI, Playwright, Motor ou Beanie.

## Contexto do Projeto

O LotoBot é uma API REST que controla uma sessão persistente do Chromium e executa o fluxo de aposta no portal Loterias Online CAIXA.

O projeto já segue Clean Architecture com as camadas:

- `domain`: entidades, enums, value objects, constantes e exceções.
- `application`: DTOs, portas, serviços de aplicação e casos de uso.
- `infrastructure`: adapters concretos para Playwright, clients HTTP, configuração, logging, seletores e banco.
- `api`: rotas FastAPI, schemas, handlers, mappers e composição de dependências.

Mantenha as dependências entre camadas:

- `domain` não depende de `application`, `api` ou `infrastructure`.
- `application` não depende de `api` ou `infrastructure`.
- `infrastructure` não depende de `api`.
- Rotas FastAPI não devem acessar diretamente Beanie, Motor ou Playwright.

## Objetivo

Implementar persistência de apostas com MongoDB usando Beanie ODM e criar os endpoints:

```http
GET /api/v1/history/bets
GET /api/v1/history/bets/{bet_id}
```

O endpoint `GET /api/v1/history/bets` deve retornar uma lista de apostas salvas e aceitar filtros opcionais:

- `lottery_modality`
- `draw_number`
- `start_date`
- `end_date`

`start_date` e `end_date` filtram o intervalo de `bet_date`.

O endpoint `GET /api/v1/history/bets/{bet_id}` deve retornar uma aposta específica pelo identificador persistido. Quando a aposta não existir, deve retornar erro padronizado `404` com `ErrorCode.NOT_FOUND`. Quando o `bet_id` for inválido, deve retornar erro padronizado `400` com `ErrorCode.BAD_REQUEST`.

## Dependências

Atualize `pyproject.toml`:

- Inclua `beanie>=1.26.0`.
- Inclua `motor>=3.4.0`.
- Inclua `anyio>=4.0.0` nas dependências runtime, pois o repositório sincroniza chamadas async do Beanie a partir de handlers sync.
- Remova duplicidade de `anyio` das dependências de desenvolvimento, se existir.

## Configuração

Atualize `.env.example` e `Settings` com:

```env
MONGODB_ENABLED=false
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=loto_bot
```

`MONGODB_ENABLED=false` deve ser o padrão seguro para não exigir MongoDB no fluxo local comum.

Atualize `.gitignore` para ignorar `db/`, usado por bancos locais.

## DTOs de Aplicação

Em `application.dto`, crie:

```python
@dataclass(frozen=True)
class BetSearchFilters:
    lottery_modality: LotteryModality | None = None
    draw_number: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass(frozen=True)
class PlacedBetResult:
    bet_id: str
    lottery_modality: LotteryModality
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime
```

Exporte esses DTOs por `application.dto.__init__` e `application.__init__`.

## Porta de Repositório

Crie `application.ports.bet_repository_port.BetRepositoryPort`:

```python
class BetRepositoryPort(Protocol):
    def save(self, lottery_modality: LotteryModality, purchase: PurchaseResult) -> None:
        """Persiste as apostas de uma compra."""

    def find_all(self, filters: BetSearchFilters) -> list[PlacedBetResult]:
        """Busca apostas pelos filtros informados."""

    def find_by_id(self, bet_id: str) -> PlacedBetResult | None:
        """Busca uma aposta pelo identificador persistido."""
```

Exporte a porta em `application.ports.__init__` e `application.__init__`.

## Service Layer

Crie `application.services.placed_bet_service.PlacedBetService`.

Responsabilidades:

- Receber `BetRepositoryPort`.
- Receber `selected_lottery_modality`.
- Resolver `LotteryModality.from_string(selected_lottery_modality)`.
- Delegar `PurchaseResult` para o repositório.
- Rejeitar modalidade inválida com `ValueError`.

Não implemente Beanie, Motor ou query Mongo nessa camada.

## Caso de Uso: Listagem de Apostas

Crie `application.use_cases.list_placed_bets.ListPlacedBetsUseCase`.

Responsabilidades:

- Receber `BetRepositoryPort` por injeção.
- Receber filtros opcionais:
  - `lottery_modality: str | None`
  - `draw_number: str | None`
  - `start_date: datetime | None`
  - `end_date: datetime | None`
- Converter `lottery_modality` para `LotteryModality` via `LotteryModality.from_string`.
- Rejeitar modalidade inválida com `ValueError`.
- Rejeitar intervalo em que `start_date > end_date` com `ValueError`.
- Criar `BetSearchFilters`.
- Retornar `list[PlacedBetResult]` a partir do repositório.

Exporte o caso de uso em `application.use_cases.__init__` e `application.__init__`.

## Caso de Uso: Consulta de Aposta por Identificador

Crie `application.use_cases.get_placed_bet.GetPlacedBetUseCase`.

Responsabilidades:

- Receber `BetRepositoryPort` por injeção.
- Receber `bet_id: str`.
- Rejeitar `bet_id` vazio ou composto apenas por espaços com `ValueError`.
- Delegar a busca para `BetRepositoryPort.find_by_id`.
- Retornar `PlacedBetResult | None`.

Não importe Beanie, Motor, PydanticObjectId ou FastAPI neste caso de uso.

Exporte o caso de uso em `application.use_cases.__init__` e `application.__init__`.

## Modelo MongoDB com Beanie

Crie `infrastructure.database.models.bet_model.BetModel` usando `beanie.Document`.

Campos obrigatórios:

```python
class BetModel(Document):
    bet_id: PydanticObjectId
    lottery_modality: LotteryModality
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime

    class Settings:
        name = "bets"
        indexes = [
            [("bet_id", 1)],
            [("lottery_modality", 1), ("bet_date", -1)],
            [("draw_number", 1)],
            [("bet_date", -1)],
        ]
```

Adicione `from_result` para montar o documento a partir de `BetResult`, `PurchaseResult` e `LotteryModality` já resolvida pelo service layer:

- `BetModel.bet_id` deve ser gerado como `PydanticObjectId()`.
- `LotteryModality` deve ser recebido como argumento, sem resolver configuração dentro do model.
- `BetResult.numbers` -> `BetModel.selected_numbers`.
- `BetResult.draw` -> `BetModel.draw_number`.
- `BetResult.status` -> `BetModel.status`.
- `BetResult.amount` -> `BetModel.bet_amount`.
- `PurchaseResult.purchase_number` -> `BetModel.purchase_number`.
- `PurchaseResult.purchase_datetime` -> `BetModel.bet_date`.

Se `BetResult.amount` for `None`, levante `ValueError`.

Adicione `to_search_result` para converter `BetModel` em `PlacedBetResult`, convertendo `bet_id` para `str`.

## Conexão MongoDB

Crie `infrastructure.database.connection.MongoDatabase`.

Responsabilidades:

- Receber `uri` e `database_name`.
- Criar `AsyncIOMotorClient`.
- Inicializar Beanie com `BetModel`.
- Evitar inicialização repetida.
- Fechar o client quando necessário.

## Repositório Beanie

Crie `infrastructure.database.repositories.beanie_bet_repository.BeanieBetRepository`.

Responsabilidades:

- Implementar `BetRepositoryPort`.
- Usar `MongoDatabase.ensure_initialized`.
- Em `save`, inserir um `BetModel` por aposta contida em `PurchaseResult.bets`.
- Em `find_all`, consultar `BetModel` usando filtros opcionais:
  - `BetModel.lottery_modality == filters.lottery_modality`
  - `BetModel.draw_number == filters.draw_number`
  - `BetModel.bet_date >= filters.start_date`
  - `BetModel.bet_date <= filters.end_date`
- Ordenar resultados por `-bet_date`.
- Em `find_by_id`, consultar `BetModel.bet_id == PydanticObjectId(bet_id)`.
- Se `bet_id` não puder ser convertido para `PydanticObjectId`, levantar `ValueError`.
- Retornar `PlacedBetResult | None` em `find_by_id`.

Como as rotas existentes são síncronas e Beanie é async:

- Use `anyio.from_thread.run` quando estiver em uma worker thread do FastAPI/AnyIO.
- Use `asyncio.run` como fallback fora do contexto ASGI.
- Feche `MongoDatabase` no fallback para evitar client preso a event loop fechado.

## Persistência no Fluxo de Aposta

Atualize `RunBetFlowUseCase`:

- Receba `bet_persistence: PlacedBetService | None = None`.
- Depois de `finish_bet`, chame persistência com o `PurchaseResult`.
- Não falhe o fluxo principal se a persistência falhar depois da compra finalizada; registre log de exception e continue notificando sucesso.
- Preserve o comportamento existente quando `bet_persistence` for `None`.

## Injeção de Dependências

Atualize `api.dependencies.AppContainer`:

- Adicione `list_placed_bets: ListPlacedBetsUseCase`.
- Adicione `get_placed_bet: GetPlacedBetUseCase`.
- Crie `MongoDatabase`.
- Crie `BeanieBetRepository`.
- Crie `ListPlacedBetsUseCase(repository=bet_repository)`.
- Crie `GetPlacedBetUseCase(repository=bet_repository)`.
- Crie `PlacedBetService` somente quando `settings.mongodb_enabled` for verdadeiro.
- Injete `bet_persistence` em `RunBetFlowUseCase`.

## API e Schemas

Atualize `api.schemas.automation_schema` com:

```python
class PlacedBetResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    bet_id: str
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime
```

Exporte `PlacedBetResponse` por `api.schemas.__init__`.

Em `api.routes.bets`, mantenha o endpoint existente:

```http
GET /api/v1/bets/run
```

Adicione:

```http
GET /api/v1/history/bets
GET /api/v1/history/bets/{bet_id}
```

Para `GET /api/v1/history/bets`, aceite os parâmetros opcionais:

- `lottery_modality: str | None`
- `draw_number: str | None`
- `start_date: datetime | None`
- `end_date: datetime | None`

Comportamento:

- Chamar `container.list_placed_bets.run(...)`.
- Converter cada `PlacedBetResult` em `PlacedBetResponse`.
- Em `ValueError`, retornar erro padronizado `400` com `ErrorCode.BAD_REQUEST`.
- Documentar respostas `200`, `400` e `500`.

Para `GET /api/v1/history/bets/{bet_id}`:

- Receber `bet_id: str` por path parameter.
- Chamar `container.get_placed_bet.run(bet_id=bet_id)`.
- Converter `PlacedBetResult` em `PlacedBetResponse`.
- Se o caso de uso retornar `None`, retornar erro padronizado `404` com `ErrorCode.NOT_FOUND`.
- Em `ValueError`, retornar erro padronizado `400` com `ErrorCode.BAD_REQUEST`.
- Documentar respostas `200`, `400`, `404` e `500`.

Registre `placed_bets_router` em `api.routes.__init__` e `api.server`.

Atualize `api.openapi.OPENAPI_TAGS` com a tag `placed-bets`.

## Page Object Model

Preserve o encapsulamento existente da automação Playwright. Não mova seletores, clicks ou parsing de telas para rotas ou casos de uso. Qualquer ajuste no fluxo do navegador deve continuar dentro da infraestrutura de browser, respeitando o estilo POM/adapters já existente.

## Testes

Atualize os testes unitários:

- Crie fake de `BetRepositoryPort`.
- Teste que `RunBetFlowUseCase` persiste a compra quando `PlacedBetService` é configurado.
- Teste que falha de persistência não quebra o fluxo principal depois da compra finalizada.
- Teste que `PlacedBetService` delega a compra com a modalidade resolvida.
- Teste que `PlacedBetService` rejeita modalidade inválida.
- Teste que `ListPlacedBetsUseCase` monta corretamente `BetSearchFilters`.
- Teste que `ListPlacedBetsUseCase` rejeita intervalo de datas inválido.
- Teste que `GetPlacedBetUseCase` delega busca por `bet_id`.
- Teste que `GetPlacedBetUseCase` rejeita `bet_id` vazio.

Atualize os testes de integração:

- Fake do container deve expor `list_placed_bets`.
- Fake do container deve expor `get_placed_bet`.
- OpenAPI deve conter `/api/v1/history/bets`.
- OpenAPI deve conter `/api/v1/history/bets/{bet_id}`.
- OpenAPI da rota de listagem deve documentar respostas `200`, `400` e `500`.
- OpenAPI da rota de detalhe deve documentar respostas `200`, `400`, `404` e `500`.
- `GET /api/v1/history/bets` deve retornar lista serializada com `bet_id`, `lottery_modality`, `selected_numbers`, `draw_number`, `status`, `bet_amount`, `purchase_number` e `bet_date`.
- Os filtros enviados por query string devem chegar ao caso de uso de listagem.
- `GET /api/v1/history/bets/{bet_id}` deve retornar uma aposta serializada.
- `GET /api/v1/history/bets/{bet_id}` deve retornar `404` quando a aposta não existir.
- `GET /api/v1/history/bets/{bet_id}` deve retornar `400` quando o identificador for inválido.

Os testes não devem abrir Chromium nem acessar `ONLINE_LOTTERY_URL`.

## Critérios de Aceite

A entrega está correta quando:

- O projeto continua seguindo Clean Architecture.
- A camada `application` não importa `infrastructure`, `api`, FastAPI, Motor ou Beanie.
- `BetModel` existe em `infrastructure.database.models.bet_model`.
- A compra finalizada pode ser persistida em MongoDB quando `MONGODB_ENABLED=true`.
- `GET /api/v1/history/bets` consulta dados persistidos por `BetModel`.
- `GET /api/v1/history/bets/{bet_id}` consulta uma aposta persistida pelo identificador.
- Os filtros opcionais funcionam isolados ou combinados.
- `start_date` e `end_date` filtram `bet_date`.
- Modalidade inválida e intervalo de datas inválido retornam erro `400`.
- `bet_id` inválido retorna erro `400`.
- Aposta inexistente retorna erro `404`.
- O endpoint `/api/v1/bets/run` permanece funcional.
- O OpenAPI documenta as novas rotas.
- Testes unitários e de integração cobrem a nova funcionalidade.

## Validação Recomendada

Execute:

```powershell
python -m pytest tests/unit/test_domain_and_use_cases.py tests/integration/test_api_routes.py tests/unit/test_architecture.py
python -m ruff format src tests
python -m ruff check --fix src tests
```

Se o ambiente local estiver com `.venv` quebrado, recrie o virtualenv antes de validar:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Observações de Segurança

- Não grave CPF, senha, CVV, dados de cartão, tokens ou códigos reais no código, em testes ou documentação.
- Use placeholders em arquivos versionáveis.
- `CONFIRM_PAYMENT=false` e `MONGODB_ENABLED=false` devem continuar sendo padrões seguros.
