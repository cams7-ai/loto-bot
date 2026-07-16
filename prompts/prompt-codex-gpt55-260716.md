# Prompt para Codex GPT-5.5: Persistencia MongoDB e Consulta de Apostas do LotoBot

Voce e um engenheiro de software senior especializado em Python 3.12, FastAPI, Clean Architecture, SOLID, Repository Pattern, Service Layer, Dependency Injection, Beanie ODM, MongoDB, Playwright e testes automatizados.

Sua missao e evoluir o projeto **LotoBot** para persistir apostas finalizadas em MongoDB e disponibilizar uma API de consulta de apostas realizadas, preservando a arquitetura existente e sem acoplar regras de aplicacao a FastAPI, Playwright ou Beanie.

## Contexto do Projeto

O LotoBot e uma API REST que controla uma sessao persistente do Chromium e executa o fluxo de aposta no portal Loterias Online CAIXA.

O projeto ja segue Clean Architecture com as camadas:

- `domain`: entidades, enums, value objects, constantes e excecoes.
- `application`: DTOs, portas, servicos de aplicacao e casos de uso.
- `infrastructure`: adapters concretos para Playwright, clients HTTP, configuracao, logging, seletores e banco.
- `api`: rotas FastAPI, schemas, handlers, mappers e composicao de dependencias.

Mantenha as dependencias entre camadas:

- `domain` nao depende de `application`, `api` ou `infrastructure`.
- `application` nao depende de `api` ou `infrastructure`.
- `infrastructure` nao depende de `api`.
- Rotas FastAPI nao devem acessar diretamente Beanie, Motor ou Playwright.

## Objetivo

Implementar persistencia de apostas com MongoDB usando Beanie ODM e criar o endpoint:

```http
GET /api/v1/placed_bets
```

Esse endpoint deve retornar uma lista de apostas salvas e aceitar filtros opcionais:

- `lottery_modality`
- `draw_number`
- `start_date`
- `end_date`

`start_date` e `end_date` filtram o intervalo de `bet_date`.

## Dependencias

Atualize `pyproject.toml`:

- Inclua `beanie>=1.26.0`.
- Inclua `motor>=3.4.0`.
- Inclua `anyio>=4.0.0` em dependencias runtime, pois o repositorio sincroniza chamadas async do Beanie a partir de handlers sync.
- Remova duplicidade de `anyio` das dependencias de desenvolvimento, se existir.

## Configuracao

Atualize `.env.example` e `Settings` com:

```env
MONGODB_ENABLED=false
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=loto_bot
```

`MONGODB_ENABLED=false` deve ser o padrao seguro para nao exigir MongoDB no fluxo local comum.

Atualize `.gitignore` para ignorar `db/`, usado por bancos locais.

## DTOs de Aplicacao

Em `application.dto`, crie:

```python
@dataclass(frozen=True)
class BetSearchFilters:
    lottery_modality: LotteryModality | None = None
    draw_number: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass(frozen=True)
class BetSearchResult:
    lottery_modality: LotteryModality
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime
```

Exporte esses DTOs por `application.__init__`.

## Porta de Repositorio

Crie `application.ports.bet_repository_port.BetRepositoryPort`:

```python
class BetRepositoryPort(Protocol):
    def save_purchase(self, lottery_modality: LotteryModality, purchase: PurchaseResult) -> None:
        """Persiste as apostas de uma compra."""

    def list_bets(self, filters: BetSearchFilters) -> list[BetSearchResult]:
        """Busca apostas pelos filtros informados."""
```

Exporte a porta em `application.ports.__init__` e `application.__init__`.

## Service Layer

Crie `application.services.bet_persistence_service.BetPersistenceService`.

Responsabilidades:

- Receber `BetRepositoryPort`.
- Receber `selected_lottery_modality`.
- Resolver `LotteryModality.from_string(selected_lottery_modality)`.
- Delegar `PurchaseResult` para o repositorio.
- Rejeitar modalidade invalida com `ValueError`.

Nao implemente Beanie, Motor ou query Mongo nessa camada.

## Caso de Uso: Listagem de Apostas

Crie `application.use_cases.list_placed_bets.ListPlacedBetsUseCase`.

Responsabilidades:

- Receber `BetRepositoryPort` por injecao.
- Receber filtros opcionais:
  - `lottery_modality: str | None`
  - `draw_number: str | None`
  - `start_date: datetime | None`
  - `end_date: datetime | None`
- Converter `lottery_modality` para `LotteryModality` via `LotteryModality.from_string`.
- Rejeitar modalidade invalida com `ValueError`.
- Rejeitar intervalo em que `start_date > end_date` com `ValueError`.
- Criar `BetSearchFilters`.
- Retornar `list[BetSearchResult]` a partir do repositorio.

Exporte o caso de uso em `application.use_cases.__init__` e `application.__init__`.

## Modelo MongoDB com Beanie

Crie `infrastructure.database.models.bet_model.BetModel` usando `beanie.Document`.

Campos obrigatorios:

```python
class BetModel(Document):
    lottery_modality: LotteryModality
    selected_numbers: list[str]
    draw_number: str
    status: str
    bet_amount: Decimal
    purchase_number: str
    bet_date: datetime

    class Settings:
        name = "bets"
```

Adicione `from_result` para montar o documento a partir de `BetResult` e `PurchaseResult`:

- `LotteryModality.from_string(self._settings.selected_lottery_modality)` deve alimentar `BetModel.lottery_modality` por meio do service layer.
- `BetResult.numbers` -> `BetModel.selected_numbers`
- `BetResult.draw` -> `BetModel.draw_number`
- `BetResult.status` -> `BetModel.status`
- `BetResult.amount` -> `BetModel.bet_amount`
- `PurchaseResult.purchase_number` -> `BetModel.purchase_number`
- `PurchaseResult.purchase_datetime` -> `BetModel.bet_date`

Se `BetResult.amount` for `None`, levante `ValueError`.

Adicione `to_search_result` para converter `BetModel` em `BetSearchResult`.

## Conexao MongoDB

Crie `infrastructure.database.connection.MongoDatabase`.

Responsabilidades:

- Receber `uri` e `database_name`.
- Criar `AsyncIOMotorClient`.
- Inicializar Beanie com `BetModel`.
- Evitar inicializacao repetida.
- Fechar o client quando necessario.

## Repositorio Beanie

Crie `infrastructure.database.repositories.beanie_bet_repository.BeanieBetRepository`.

Responsabilidades:

- Implementar `BetRepositoryPort`.
- Usar `MongoDatabase.ensure_initialized`.
- Em `save_purchase`, inserir um `BetModel` por aposta contida em `PurchaseResult.bets`.
- Em `list_bets`, consultar `BetModel` usando filtros opcionais:
  - `BetModel.lottery_modality == filters.lottery_modality`
  - `BetModel.draw_number == filters.draw_number`
  - `BetModel.bet_date >= filters.start_date`
  - `BetModel.bet_date <= filters.end_date`
- Ordenar resultados por `-bet_date`.
- Retornar `list[BetSearchResult]`.

Como as rotas existentes sao sincronas e Beanie e async:

- Use `anyio.from_thread.run` quando estiver em uma worker thread do FastAPI/AnyIO.
- Use `asyncio.run` como fallback fora do contexto ASGI.
- Feche `MongoDatabase` no fallback para evitar client preso a event loop fechado.

## Persistencia no Fluxo de Aposta

Atualize `RunBetFlowUseCase`:

- Receba `bet_persistence: BetPersistenceService | None = None`.
- Depois de `finish_bet`, chame persistencia com o `PurchaseResult`.
- Nao falhe o fluxo principal se a persistencia falhar depois da compra finalizada; registre log de exception e continue notificando sucesso.
- Preserve o comportamento existente quando `bet_persistence` for `None`.

## Injecao de Dependencias

Atualize `api.dependencies.AppContainer`:

- Adicione `list_placed_bets: ListPlacedBetsUseCase`.
- Crie `MongoDatabase`.
- Crie `BeanieBetRepository`.
- Crie `ListPlacedBetsUseCase(repository=bet_repository)`.
- Crie `BetPersistenceService` somente quando `settings.mongodb_enabled` for verdadeiro.
- Injete `bet_persistence` em `RunBetFlowUseCase`.

## API e Schemas

Atualize `api.schemas.automation_schema` com:

```python
class PlacedBetResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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

Crie um segundo router:

```python
placed_bets_router = APIRouter(prefix="/api/v1/placed_bets", tags=["placed-bets"])
```

Adicione:

```http
GET /api/v1/placed_bets
```

Parametros opcionais:

- `lottery_modality: str | None`
- `draw_number: str | None`
- `start_date: datetime | None`
- `end_date: datetime | None`

Comportamento:

- Chamar `container.list_placed_bets.run(...)`.
- Converter `BetSearchResult` em `PlacedBetResponse`.
- Em `ValueError`, retornar erro padronizado `400` com `ErrorCode.BAD_REQUEST`.
- Documentar respostas `400` e `500`.

Registre `placed_bets_router` em `api.routes.__init__` e `api.server`.

Atualize `api.openapi.OPENAPI_TAGS` com a tag `placed-bets`.

## Page Object Model

Preserve o encapsulamento existente da automacao Playwright. Nao mova seletores, clicks ou parsing de telas para rotas ou casos de uso. Qualquer ajuste no fluxo do navegador deve continuar dentro da infraestrutura de browser, respeitando o estilo POM/adapters ja existente.

## Testes

Atualize os testes unitarios:

- Crie fake de `BetRepositoryPort`.
- Teste que `RunBetFlowUseCase` persiste a compra quando `BetPersistenceService` e configurado.
- Teste que `BetPersistenceService` delega a compra com a modalidade resolvida.
- Teste que `ListPlacedBetsUseCase` monta corretamente `BetSearchFilters`.
- Teste que `ListPlacedBetsUseCase` rejeita intervalo de datas invalido.

Atualize os testes de integracao:

- Fake do container deve expor `list_placed_bets`.
- OpenAPI deve conter `/api/v1/placed_bets`.
- OpenAPI da rota deve documentar respostas `200`, `400` e `500`.
- `GET /api/v1/placed_bets` deve retornar lista serializada com `lottery_modality`, `selected_numbers`, `draw_number`, `status`, `bet_amount`, `purchase_number` e `bet_date`.
- Os filtros enviados por query string devem chegar ao caso de uso.

Os testes nao devem abrir Chromium nem acessar `ONLINE_LOTTERY_URL`.

## Criterios de Aceite

A entrega esta correta quando:

- O projeto continua seguindo Clean Architecture.
- A camada `application` nao importa `infrastructure`, `api`, FastAPI, Motor ou Beanie.
- `BetModel` existe em `infrastructure.database.models.bet_model`.
- A compra finalizada pode ser persistida em MongoDB quando `MONGODB_ENABLED=true`.
- `GET /api/v1/placed_bets` consulta dados persistidos por `BetModel`.
- Os filtros opcionais funcionam isolados ou combinados.
- `start_date` e `end_date` filtram `bet_date`.
- Modalidade invalida e intervalo de datas invalido retornam erro `400`.
- O endpoint `/api/v1/bets/run` permanece funcional.
- O OpenAPI documenta a nova rota.
- Testes unitarios e de integracao cobrem a nova funcionalidade.

## Validacao Recomendada

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

## Observacoes de Seguranca

- Nao grave CPF, senha, CVV, dados de cartao, tokens ou codigos reais no codigo, em testes ou documentacao.
- Use placeholders em arquivos versionaveis.
- `CONFIRM_PAYMENT=false` e `MONGODB_ENABLED=false` devem continuar sendo padroes seguros.
