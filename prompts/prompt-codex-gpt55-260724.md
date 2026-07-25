# Prompt para Codex GPT-5.5: Busca de Apostas no Portal Loterias Online CAIXA

Você é um engenheiro de software sênior especializado em Python 3.12, FastAPI, Clean Architecture, SOLID, Repository Pattern, Service Layer, Dependency Injection, Playwright e testes automatizados.

A sua missão é evoluir o projeto **LotoBot** para buscar as apostas diretamente no portal Loterias Online CAIXA, preservando a arquitetura existente e sem acoplar regras de aplicação a FastAPI ou Playwright.

Toda a lógica interna do código deve ser escrita em inglês, incluindo nomes de classes, funções, métodos, módulos, variáveis e objetos de domínio. Comentários no código, mensagens de erro, logs personalizados, documentação técnica, README e demais textos direcionados ao usuário ou mantenedor devem ser escritos em português do Brasil.

Antes de alterar qualquer arquivo, leia o código atual, os testes, `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md` e `pyproject.toml`. Preserve mudanças locais do usuário e adapte a implementação ao estado real do repositório.

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
- Rotas FastAPI não devem acessar diretamente Playwright, Beanie, Motor ou clients HTTP.
- A camada `api` não deve importar Playwright.
- Seletores, navegação, espera, escolha de opções e parsing do DOM pertencem à infraestrutura.

Os testes de arquitetura em `tests/unit/test_architecture.py` validam essas regras com `grimp` e devem continuar passando.

## Estado Atual que Deve Ser Preservado

O projeto já possui:

- `GET /api/v1/sessions/start`, `GET /api/v1/sessions/stop` e `GET /api/v1/sessions/status`.
- `POST /api/v1/bets/run` para executar uma aposta.
- `GET /api/v1/history/bets` e `GET /api/v1/history/bets/{bet_id}` para consultar o histórico persistido no MongoDB.
- `BetSearchFilters`, `PlacedBetResult`, `BetRepositoryPort`, `ListPlacedBetsUseCase` e `GetPlacedBetUseCase` para o histórico persistido.
- `PlaywrightBrowserAutomation`, composto por mixins e executado em uma thread exclusiva por `_run_on_browser_thread`.
- `Selectors` para centralizar seletores do portal.
- `AppContainer` para compartilhar a mesma `AutomationSession` e a mesma instância do adapter Playwright entre casos de uso.
- Respostas de erro padronizadas com `ApiError`, `ApiExceptionMapper`, `ErrorCode` e `error_response`.
- Datas do portal normalizadas para o timezone `America/Sao_Paulo`.
- Cobertura mínima configurada em 100%.

A nova funcionalidade é uma **consulta ao vivo no portal**. Ela não substitui nem reutiliza indevidamente o histórico MongoDB:

- Não altere o significado de `GET /api/v1/history/bets`.
- Não use `BetRepositoryPort` para a consulta ao vivo.
- Não persista automaticamente os resultados obtidos no portal.
- Não renomeie `PlacedBetResult` nem `ListPlacedBetsUseCase`.
- Use nomes explícitos como `PortalBetSearchFilters`, `PortalBetResult`, `PortalBetQueryPort` e `ListPortalBetsUseCase` para evitar colisões semânticas.

## Objetivo

Implemente:

```http
GET /api/v1/bets
```

O endpoint deve acessar:

```text
https://www.loteriasonline.caixa.gov.br/silce-web/#/apostas
```

e retornar as apostas exibidas na tabela do portal.

O endpoint deve aceitar os seguintes parâmetros opcionais:

- `bet_type`: tipo de aposta.
- `lottery_modality`: modalidade.
- `draw_type`: tipo de concurso.
- `month_year`: mês/ano ou período relativo.
- `status`: situação.
- `sort_by`: ordenação.

Exemplo com valores canônicos:

```http
GET /api/v1/bets?bet_type=individual&lottery_modality=MEGA_SENA&draw_type=normal&month_year=2026-07&status=paid&sort_by=date-desc
```

Preserve também:

```http
POST /api/v1/bets/run
GET /api/v1/history/bets
GET /api/v1/history/bets/{bet_id}
```

## Pré-condição e Ciclo de Vida da Sessão

`GET /api/v1/bets` deve usar a sessão persistente já controlada pelo LotoBot.

- Exija uma sessão aberta antes de consultar o portal.
- Quando a sessão estiver fechada, levante `BrowserSessionClosedError` e retorne o erro padronizado `409` com `ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE`.
- Não inicie, autentique, feche ou reinicie o Chromium automaticamente dentro desse endpoint.
- Não encerre a sessão após uma consulta bem-sucedida.
- A rota não deve chamar diretamente o controle de sessão.
- A consulta pressupõe que `GET /api/v1/sessions/start` já iniciou e autenticou a sessão.
- Se a sessão do portal tiver expirado ou houver redirecionamento inesperado, use o tratamento de automação já existente; não tente contornar autenticação, CAPTCHA ou bloqueios do portal.

## Contrato dos Filtros

Use valores canônicos e estáveis na API e converta-os para os rótulos visíveis do portal somente no adapter de infraestrutura. A exceção é `lottery_modality`, cujo contrato público deve usar diretamente os nomes de modalidade listados na seção correspondente. Não exponha os valores internos do Angular, como `number:1`, `number:2` ou `72026`, como contrato público.

Nos demais filtros, além dos valores canônicos descritos abaixo, aceite os rótulos exatos em português do portal como aliases públicos de entrada, ignorando espaços externos e diferenças de maiúsculas/minúsculas. Para `lottery_modality`, os nomes exibidos no portal já são os próprios valores públicos. O OpenAPI, o README e os exemplos devem documentar essa diferença.

Como esses rótulos também fazem parte do contrato público como aliases, a camada de aplicação pode conhecer um catálogo de normalização sem qualquer referência a XPath, DOM ou Playwright. Centralize esse catálogo em um único módulo independente de framework. A tradução final do enum tipado para o rótulo usado em `select_option` continua sendo responsabilidade da infraestrutura. Não espalhe os mesmos dicionários por rota, caso de uso, adapter e testes.

### `bet_type`

| Valor da API | Rótulo no portal |
|---|---|
| `all` | `Todas` |
| `individual` | `Aposta Individual` |
| `pool` | `Aposta Bolão` |

Elemento:

```xpath
//select[@id='tipoAposta']
```

### `lottery_modality`

Para esse parâmetro, reutilize o enum de domínio `LotteryModality`. Não crie um enum duplicado como `PortalLotteryModality`.

Os valores aceitos pela API e selecionados no portal são:

| Valor de `lottery_modality` | Mapeamento interno |
|---|---|
| `Todas` | ausência de modalidade específica (`None`) |
| `Dia de Sorte` | `LotteryModality.DIA_DE_SORTE` |
| `Dupla Sena` | `LotteryModality.DUPLA_SENA` |
| `Loteca` | `LotteryModality.LOTECA` |
| `Lotofácil` | `LotteryModality.LOTOFACIL` |
| `Lotomania` | `LotteryModality.LOTOMANIA` |
| `+Milionária` | `LotteryModality.MAIS_MILIONARIA` |
| `Mega-Sena` | `LotteryModality.MEGA_SENA` |
| `Quina` | `LotteryModality.QUINA` |
| `Super Sete` | `LotteryModality.SUPER_SETE` |
| `Timemania` | `LotteryModality.TIMEMANIA` |

Elemento:

```xpath
//select[@id='modalidades']
```

O método existente `LotteryModalityBuilder.get_lottery_modality` deve continuar inalterado, pois atende ao fluxo de navegação e atualmente retorna:

```text
"mega-sena"
"quina"
"quina de são joão"
"loteca"
"loteca especial"
"lotofácil"
"lotofácil da independência"
"+milionária"
"lotomania"
"timemania"
"dupla sena"
"dia de sorte"
"super sete"
```

Para o novo filtro, crie um mapper específico de infraestrutura, por exemplo `PortalLotteryModalityBuilder` ou `LotteryModalityFilterBuilder`, que receba `LotteryModality | None` e retorne exatamente:

```text
"Todas"
"Dia de Sorte"
"Dupla Sena"
"Loteca"
"Lotofácil"
"Lotomania"
"+Milionária"
"Mega-Sena"
"Quina"
"Super Sete"
"Timemania"
```

Não altere capitalização, acentuação ou espaçamento desses rótulos. Não aceite `QUINA_ESPECIAL`, `LOTECA_ESPECIAL` ou `LOTOFACIL_ESPECIAL`, pois essas modalidades não estão disponíveis no `<select id="modalidades">`.

### `draw_type`

| Valor da API | Rótulo no portal |
|---|---|
| `all` | `Todos` |
| `normal` | `Normal` |
| `special` | `Especial` |

Elemento:

```xpath
//select[@id='tipoConcurso']
```

O elemento é renderizado condicionalmente pelo Angular. Se `draw_type` for informado, selecione primeiro `lottery_modality`, aguarde a estabilização do DOM e somente depois tente selecionar o tipo de concurso. Se a combinação escolhida não disponibilizar o campo, retorne erro de entrada claro e padronizado em vez de ignorar silenciosamente o filtro.

### `month_year`

| Valor da API | Rótulo no portal |
|---|---|
| `last-7-days` | `Últimos 7 dias` |
| `last-15-days` | `Últimos 15 dias` |
| `last-30-days` | `Últimos 30 dias` |
| `last-45-days` | `Últimos 45 dias` |
| `last-90-days` | `Últimos 90 dias` |
| `YYYY-MM`, dentro da janela móvel permitida | nome do mês em português seguido de `/YYYY` |

Elemento:

```xpath
//select[@id='periodos']
```

Os valores de calendário devem ser calculados dinamicamente a partir da data corrente em `America/Sao_Paulo`. Aceite somente o mês corrente e os cinco meses imediatamente anteriores, totalizando seis opções.

Exemplos:

- Em qualquer dia de julho de 2026, os valores válidos são `2026-07`, `2026-06`, `2026-05`, `2026-04`, `2026-03` e `2026-02`.
- Em qualquer dia de agosto de 2026, os valores válidos passam a ser `2026-08`, `2026-07`, `2026-06`, `2026-05`, `2026-04` e `2026-03`.
- Em janeiro de 2027, os valores válidos são `2027-01`, `2026-12`, `2026-11`, `2026-10`, `2026-09` e `2026-08`.

Regras de validação:

- Valide o formato estrito `YYYY-MM`, com mês entre `01` e `12`.
- Calcule meses de calendário; não aproxime um mês subtraindo 30 dias.
- Recalcule a janela pela data corrente a cada execução do caso de uso. Não fixe a lista no carregamento do módulo ou na inicialização da aplicação.
- Rejeite meses futuros, meses anteriores à janela móvel e datas malformadas com `ValueError` antes de chamar o adapter Playwright.
- Os períodos relativos `last-7-days`, `last-15-days`, `last-30-days`, `last-45-days` e `last-90-days` continuam sempre válidos.
- Se aceitar o rótulo localizado como alias, como `Julho/2026`, converta-o para `2026-07` e aplique a mesma janela móvel.

Centralize a conversão do mês canônico para o rótulo em português:

| Mês | Nome no portal |
|---:|---|
| `01` | `Janeiro` |
| `02` | `Fevereiro` |
| `03` | `Março` |
| `04` | `Abril` |
| `05` | `Maio` |
| `06` | `Junho` |
| `07` | `Julho` |
| `08` | `Agosto` |
| `09` | `Setembro` |
| `10` | `Outubro` |
| `11` | `Novembro` |
| `12` | `Dezembro` |

Assim, `2026-08` deve selecionar por label `Agosto/2026`. Não espalhe nomes de meses ou valores internos do `<option>` pelo adapter. Depois da validação da aplicação, confirme também que o rótulo calculado existe no `<select>` atual antes de aplicá-lo.

Use um relógio injetável, como uma porta `ClockPort` ou um `today_provider`, para que a camada de aplicação obtenha a data corrente de forma determinística e testável. A implementação concreta deve usar `America/Sao_Paulo`. Não adicione biblioteca externa apenas para subtrair meses.

### `status`

| Valor da API | Rótulo no portal |
|---|---|
| `all` | `Todas` |
| `paid` | `Pagas` |
| `expired` | `Prescritas` |

Elemento:

```xpath
//select[@id='situacoes']
```

### `sort_by`

| Valor da API | Rótulo no portal |
|---|---|
| `date-asc` | `Data Crescente` |
| `date-desc` | `Data Decrescente` |

Elemento:

```xpath
//select[@id='ordenacoes']
```

### Validação

- Resolva e valide os valores na camada de aplicação, sem importar FastAPI ou Playwright.
- Rejeite valores desconhecidos com `ValueError` e uma mensagem que identifique o parâmetro e os valores permitidos.
- Converta `ValueError` em resposta padronizada `400` com `ErrorCode.BAD_REQUEST`.
- Valide todos os parâmetros antes de navegar ou interagir com o portal.
- Um filtro inválido não pode acionar o adapter Playwright.

## Semântica de Aplicação dos Filtros

Os valores padrão do portal são:

- `bet_type=all`.
- `lottery_modality=all`.
- `draw_type=all`.
- `month_year=last-7-days`.
- `status=all`.
- `sort_by=date-desc`.

O comportamento deve ser determinístico mesmo com uma sessão persistente:

1. Acesse a página de apostas.
2. Aguarde o formulário de filtros estar disponível.
3. Garanta que parâmetros omitidos não herdem seleções de uma requisição anterior.
4. Quando nenhum parâmetro for informado e a página já estiver nos padrões, não clique desnecessariamente em `Aplicar`.
5. Quando ao menos um parâmetro for informado, restaure os valores padrão dos campos omitidos, aplique os valores recebidos e clique uma única vez no botão:

```xpath
//button[@id='aplicarFiltro']
```

6. Se for necessário restaurar filtros antigos mesmo sem parâmetros, aplique os padrões e clique uma única vez.
7. Não use o botão `Limpar Filtros` como substituto para a montagem explícita e testável dos filtros, salvo se o comportamento real do portal exigir isso e estiver coberto por teste.

Use `select_option(label=...)` ou mecanismo equivalente por rótulo. Não selecione pelas strings internas geradas pelo Angular.

## Contrato de Resposta

Para cada linha da tabela, retorne:

- `purchase_datetime`: `Data/Hora da Compra`, como `datetime` com timezone de São Paulo.
- `lottery_modality`: texto de `Modalidade`.
- `selected_numbers`: valores exibidos em `Aposta`, preservando zeros à esquerda e a ordem do DOM.
- `draw_number`: texto de `Concurso`.
- `status`: texto normalizado de `Situação`.

Exemplo:

```json
[
  {
    "purchase_datetime": "2026-07-19T12:33:09-03:00",
    "lottery_modality": "Mega-Sena",
    "selected_numbers": ["09", "18", "33", "40", "47", "53"],
    "draw_number": "3034",
    "status": "Aposta não premiada"
  },
  {
    "purchase_datetime": "2026-07-17T22:09:36-03:00",
    "lottery_modality": "Super Sete",
    "selected_numbers": ["5", "2", "1", "8", "5", "8", "1"],
    "draw_number": "875",
    "status": "Aposta não premiada"
  }
]
```

Regras:

- Não retorne o identificador oculto da aposta, porque ele não faz parte do requisito.
- Não retorne a coluna `Ação`.
- Não retorne textos do botão `Resultados`, cabeçalhos do Super Sete ou conteúdo de modais ocultos como parte de `selected_numbers`.
- Preserve a ordem das linhas entregue pelo portal; não faça uma segunda ordenação na API.
- Quando a pesquisa válida não tiver apostas, retorne `200` com `[]`.
- Não retorne linhas parcialmente preenchidas. Uma linha malformada deve gerar falha de automação clara.

## Enums e DTOs

Crie enums ou value objects tipados para os demais filtros, com valores canônicos independentes dos valores internos dos `<option>` do Angular. Para modalidade, reutilize obrigatoriamente `LotteryModality` e mantenha a conversão dos nomes públicos sem dependência de FastAPI, Playwright ou infrastructure.

Não modele os seis meses de calendário em um enum fixo. Use um value object equivalente a:

```python
@dataclass(frozen=True, order=True)
class PortalYearMonth:
    year: int
    month: int

    @property
    def canonical_value(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"
```

Mantenha os cinco períodos relativos em um enum separado ou modele ambos em um tipo de período que não congele os meses disponíveis.

Em `application.dto`, crie DTOs equivalentes a:

```python
@dataclass(frozen=True)
class PortalBetSearchFilters:
    bet_type: PortalBetType | None = None
    lottery_modality: LotteryModality | None = None
    draw_type: PortalDrawType | None = None
    month_year: PortalBetRelativePeriod | PortalYearMonth | None = None
    status: PortalBetStatus | None = None
    sort_by: PortalBetSortOrder | None = None
    has_explicit_filters: bool = False

    @property
    def has_filters(self) -> bool:
        """Indica se ao menos um filtro foi explicitamente informado."""
        return self.has_explicit_filters


@dataclass(frozen=True)
class PortalBetResult:
    purchase_datetime: datetime
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
```

Os nomes concretos podem ser ajustados para seguir a convenção existente, mas não reutilize `BetSearchFilters` ou `PlacedBetResult`, pois esses DTOs representam dados persistidos.

`Todas` deve ser convertida em `lottery_modality=None`. Como `None` também representa parâmetro omitido, preserve separadamente a informação de que algum filtro foi explicitamente recebido; não derive `has_filters` apenas dos valores já normalizados.

Exporte os novos tipos pelos respectivos `__init__.py` de `domain.enums`, `domain`, `application.dto` e `application`, conforme a camada em que forem definidos.

## Porta de Consulta ao Portal

Crie uma porta específica, por exemplo `application.ports.portal_bet_query_port.PortalBetQueryPort`:

```python
class PortalBetQueryPort(Protocol):
    def find_all(
        self,
        session: AutomationSession,
        filters: PortalBetSearchFilters,
    ) -> list[PortalBetResult]:
        """Busca no portal as apostas que atendem aos filtros."""
```

Responsabilidades:

- Expor apenas a operação necessária ao caso de uso.
- Usar tipos de domínio e aplicação.
- Não importar Playwright, FastAPI, Pydantic, Beanie ou Motor.
- Não herdar de `BetRepositoryPort`.

Crie também uma abstração mínima de relógio, por exemplo:

```python
class ClockPort(Protocol):
    def today(self) -> date:
        """Retorna a data corrente no timezone configurado pela implementação."""
```

Implemente-a na infraestrutura com `datetime.now(sao_paulo_timezone()).date()`, reutilizando os utilitários existentes. A implementação deve calcular a data a cada chamada.

Exporte as portas em `application.ports.__init__` e `application.__init__`.

## Caso de Uso

Crie `application.use_cases.list_portal_bets.ListPortalBetsUseCase`.

Responsabilidades:

- Receber `AutomationSession` e `PortalBetQueryPort` por injeção.
- Receber um relógio ou provedor de data corrente por injeção.
- Receber os seis parâmetros como `str | None`.
- Normalizar aliases e converter os valores para os tipos de filtro.
- Converter os nomes públicos de `lottery_modality` para o `LotteryModality` correspondente e converter `Todas` em `None`.
- Rejeitar as variantes especiais de `LotteryModality` que não existem no filtro do portal.
- Converter `month_year` relativo para `PortalBetRelativePeriod` ou `YYYY-MM` para `PortalYearMonth`.
- Validar `PortalYearMonth` contra o mês corrente e os cinco anteriores usando a data fornecida pelo relógio.
- Rejeitar todos os valores inválidos antes de chamar a porta.
- Exigir que a sessão esteja aberta.
- Criar `PortalBetSearchFilters`.
- Marcar a operação da sessão como uma nova operação explícita, por exemplo `Operation.LIST_PORTAL_BETS = "Busca apostas no portal"`.
- Delegar a consulta para `PortalBetQueryPort.find_all`.
- Retornar `list[PortalBetResult]`.
- Após sucesso, devolver a sessão ao estado aberto/ocioso sem apagar a última operação executada.
- Não importar FastAPI, Playwright ou infrastructure.
- Não consultar MongoDB.
- Não iniciar ou encerrar a sessão.

Para falhas:

- Preserve `AutomationError` e erros de redirecionamento já tipados.
- Converta falhas inesperadas do adapter em erro de automação padronizado sem importar Playwright.
- Marque a sessão como falha quando a operação de automação falhar.
- Não feche automaticamente a sessão persistente por causa de uma falha nessa consulta.

Hoje, `OperationExecutor._execute` marca a sessão como `RUNNING` e `AutomationSession.mark_open()` troca a operação para `START_SESSION`. Não deixe a sessão presa em `RUNNING` depois da resposta. Modele na entidade uma transição explícita, por exemplo `mark_ready()` ou `mark_operation_completed()`, que restaure `AutomationStatus.OPEN` preservando `executed_operation`. Não altere `session.status` diretamente no caso de uso.

Exporte o caso de uso em `application.use_cases.__init__` e `application.__init__`.

## Configuração

Adicione a configuração do caminho da página sem duplicar a URL base:

```env
PORTAL_BETS_PATH=/apostas
```

Em `Settings`, adicione um campo equivalente a:

```python
portal_bets_path: str = Field(default="/apostas", alias="PORTAL_BETS_PATH")
```

Crie uma propriedade derivada que componha:

```text
ONLINE_LOTTERY_URL + ONLINE_LOTTERY_PATH + PORTAL_BETS_PATH
```

O resultado padrão deve ser:

```text
https://www.loteriasonline.caixa.gov.br/silce-web/#/apostas
```

Atualize `.env.example`. Não grave a URL completa diretamente no caso de uso, na rota ou no adapter.

## Seletores

Centralize em `infrastructure.selectors.Selectors`:

```python
PORTAL_BET_TYPE_FILTER = "//select[@id='tipoAposta']"
PORTAL_LOTTERY_MODALITY_FILTER = "//select[@id='modalidades']"
PORTAL_DRAW_TYPE_FILTER = "//select[@id='tipoConcurso']"
PORTAL_PERIOD_FILTER = "//select[@id='periodos']"
PORTAL_STATUS_FILTER = "//select[@id='situacoes']"
PORTAL_SORT_FILTER = "//select[@id='ordenacoes']"
PORTAL_APPLY_FILTER_BUTTON = "//button[@id='aplicarFiltro']"
PORTAL_BETS_TABLE = "//table[@id='tabelaApostas']"
PORTAL_BETS_TABLE_ROWS = "//table[@id='tabelaApostas']/tbody/tr[td]"
```

Adicione seletores row-scoped ou helpers para as células da tabela. Evite seletores globais para elementos repetidos.

Crie mappers/builders de infraestrutura para converter os filtros nos rótulos do portal. Para modalidade, use o mapper específico descrito na seção `lottery_modality`; não modifique nem reaproveite de forma incorreta `LotteryModalityBuilder.get_lottery_modality`, pois seus valores em minúsculas atendem a outra finalidade.

## Adapter Playwright e Page Object

Preserve o padrão atual de mixins. Crie um componente equivalente a:

```text
infrastructure/browser/portal_bets_browser.py
```

e componha-o em `PlaywrightBrowserAutomation`.

O método público da porta deve enviar toda a operação Playwright para `_run_on_browser_thread`, usando a mesma thread e a mesma página da sessão persistente.

Fluxo esperado:

1. Obter a página ativa com `_require_page`.
2. Navegar para a URL derivada de `Settings`.
3. Validar o redirecionamento para `/apostas`.
4. Aguardar o formulário e a tabela por condições do DOM.
5. Resolver os rótulos dos filtros no mapper de infraestrutura.
6. Restaurar os padrões dos campos omitidos quando a aplicação de filtros for necessária.
7. Selecionar a modalidade antes do tipo de concurso.
8. Selecionar opções por `label`.
9. Clicar uma única vez em `Aplicar`, quando necessário.
10. Aguardar a atualização real da tabela.
11. Extrair e converter todas as linhas.

Não use `time.sleep` nem esperas fixas arbitrárias. Prefira:

- `locator.wait_for`;
- `page.wait_for_url`;
- uma condição de atualização do conteúdo da tabela;
- o desaparecimento de um indicador de carregamento, se existir;
- ou uma resposta/requisição específica do portal, se isso puder ser feito sem acoplamento frágil.

Não use `networkidle` como única evidência de que uma SPA Angular terminou de renderizar.

## Parsing da Tabela

A tabela possui a seguinte estrutura:

| Índice DOM da célula | Conteúdo |
|---:|---|
| `0` | identificador oculto, fora da resposta |
| `1` | data e hora, em dois elementos `<h6>` |
| `2` | modalidade |
| `3` | aposta |
| `4` | concurso |
| `5` | situação |
| `6` | ações, fora da resposta |

Use sempre a linha atual como escopo:

```text
#tabelaApostas tbody tr
  -> td da própria linha
  -> elementos da própria célula
```

Regras de parsing:

- Leia a data e a hora separadamente e use o utilitário já existente para criar um `datetime` no timezone `America/Sao_Paulo`.
- Normalize apenas espaços supérfluos; não remova acentos nem zeros à esquerda.
- Para apostas numéricas comuns, leia os `span.margemVolante` da célula da aposta.
- Para Super Sete, leia somente os `span.margemVolante` das colunas, em ordem. Não inclua os spans do cabeçalho `1` a `7`.
- O HTML repete `id="numeros-selecionados"` em várias linhas. Nunca use esse ID globalmente para extrair apostas.
- Para modalidades com marcação alternativa, extraia apenas as seleções visíveis dentro da célula da aposta e cubra o formato com testes. Não inclua `Resultados`, conteúdo do modal de troca ou texto da coluna de ação.
- Leia concurso e situação como strings limpas.
- Verifique a quantidade de células e os campos obrigatórios antes de construir o resultado.
- Se `tbody` não tiver linhas de aposta após uma pesquisa concluída, retorne lista vazia.

Não use BeautifulSoup nem adicione dependências se os locators do Playwright forem suficientes.

## Injeção de Dependências

Atualize `api.dependencies.AppContainer`:

- Adicione `list_portal_bets: ListPortalBetsUseCase`.
- Use a mesma instância de `AutomationSession` já criada pelo container.
- Use a mesma instância de `PlaywrightBrowserAutomation` já injetada nos demais casos de uso.
- Injete o adapter como implementação estrutural de `PortalBetQueryPort`.
- Injete a implementação do relógio em `ListPortalBetsUseCase`; ela deve consultar a data corrente em `America/Sao_Paulo` quando chamada, e não armazenar uma data calculada durante o startup.
- Não crie uma segunda sessão, página, thread ou instância de Chromium para a consulta.

Preserve `list_placed_bets` e `get_placed_bet`.

## API e Schema

Em `api.schemas.automation_schema`, crie:

```python
class PortalBetResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "purchase_datetime": "2026-07-19T12:33:09-03:00",
                "lottery_modality": "Mega-Sena",
                "selected_numbers": ["09", "18", "33", "40", "47", "53"],
                "draw_number": "3034",
                "status": "Aposta não premiada",
            }
        },
    )

    purchase_datetime: datetime
    lottery_modality: str
    selected_numbers: list[str]
    draw_number: str
    status: str
```

Exporte o schema por `api.schemas.__init__`.

Em `api.routes.bets`, adicione ao router existente:

```http
GET /api/v1/bets
```

Diretrizes:

- Use handler síncrono `def`, pois o adapter atual usa Playwright síncrono e o FastAPI executará o handler em worker thread.
- Aceite os seis parâmetros opcionais como query strings.
- Documente descrições, valores canônicos e exemplos com `Query`; para `lottery_modality`, documente exatamente `Todas`, `Dia de Sorte`, `Dupla Sena`, `Loteca`, `Lotofácil`, `Lotomania`, `+Milionária`, `Mega-Sena`, `Quina`, `Super Sete` e `Timemania`.
- Para `month_year`, documente os cinco períodos relativos e o formato dinâmico `YYYY-MM`, deixando claro que apenas o mês corrente e os cinco anteriores são aceitos. Não publique uma enumeração estática de meses no OpenAPI.
- Delegue para `container.list_portal_bets.run(...)`.
- Converta `PortalBetResult` para `PortalBetResponse`.
- Garanta timezone de São Paulo e remova microssegundos na serialização, seguindo a convenção atual.
- Converta `ValueError` em `ApiError` `400` com `ErrorCode.BAD_REQUEST`.
- Converta `AutomationError` por `ApiExceptionMapper`.
- Não capture `Exception` genericamente na rota; use o handler global.

Documente no OpenAPI:

- `200`: lista retornada, inclusive vazia.
- `400`: filtro inválido ou combinação de filtros não aplicável.
- `409`: sessão do navegador fechada.
- `500`: erro interno ou falha de automação.
- `502`: redirecionamento inesperado do portal.
- `503`: serviço externo indisponível, se o fluxo atual puder produzir esse erro.

Mantenha a tag `bets`, atualizando sua descrição em `api.openapi.OPENAPI_TAGS` para abranger execução de apostas e consulta ao vivo. A tag `placed-bets` continua reservada ao histórico persistido.

## Concorrência

O browser é um recurso compartilhado e stateful:

- Toda interação Playwright deve continuar serializada pelo executor de uma única thread já existente.
- Não execute locators a partir da thread do handler FastAPI.
- Não crie paralelismo interno para selecionar filtros ou ler linhas.
- Uma requisição não pode observar filtros parcialmente aplicados por outra.
- Se for necessário adicionar um lock de aplicação, mantenha-o no adapter ou serviço responsável pelo recurso compartilhado, nunca na rota.

## Testes Unitários

Atualize os testes sem abrir Chromium real:

- Crie fake de `PortalBetQueryPort`.
- Crie fake mutável de `ClockPort` para controlar a data sem alterar o relógio global do processo.
- Teste que `ListPortalBetsUseCase` exige sessão aberta.
- Teste que a sessão volta para `AutomationStatus.OPEN` após uma consulta bem-sucedida e preserva `Operation.LIST_PORTAL_BETS`.
- Teste que uma falha de automação marca a sessão como `AutomationStatus.FAILED` sem fechá-la.
- Teste que o caso de uso converte todos os valores canônicos dos demais filtros.
- Teste a conversão de cada valor público de `lottery_modality` para `LotteryModality`.
- Teste que `Todas` resulta em `lottery_modality=None` sem perder `has_explicit_filters=True`.
- Teste que `QUINA_ESPECIAL`, `LOTECA_ESPECIAL` e `LOTOFACIL_ESPECIAL` são rejeitadas.
- Teste aliases com acentos nos demais filtros, como `Aposta Bolão`, `Últimos 7 dias` e `Prescritas`.
- Teste trim e normalização de maiúsculas/minúsculas.
- Com relógio fixado em julho de 2026, teste que `2026-07` até `2026-02` são aceitos.
- Com relógio fixado em agosto de 2026, teste que `2026-08` até `2026-03` são aceitos e que `2026-02` deixa de ser válido.
- Teste a virada de ano: em janeiro de 2027, aceite `2027-01` e `2026-12` até `2026-08`.
- Teste rejeição de mês futuro, mês anterior à janela, mês `00`, mês `13` e formatos diferentes de `YYYY-MM`.
- Teste que os cinco períodos relativos permanecem válidos independentemente da data corrente.
- Teste que o relógio é consultado em cada execução, permitindo que uma instância viva do caso de uso atravesse a mudança de mês.
- Teste o mapper de todos os doze nomes de meses em português e a conversão `YYYY-MM` -> `Nome do mês/YYYY`.
- Teste individualmente cada parâmetro inválido.
- Teste que filtro inválido não chama a porta.
- Teste a construção de `PortalBetSearchFilters`.
- Teste que resultados e lista vazia são retornados sem transformação indevida.
- Teste o novo valor de `Operation`.
- Teste o mapper completo entre valores canônicos e rótulos do portal.
- Teste que o novo mapper de modalidade retorna exatamente os onze rótulos permitidos, incluindo `Todas`.
- Adicione teste de regressão garantindo que `LotteryModalityBuilder.get_lottery_modality` mantém seus treze retornos atuais, incluindo as três modalidades especiais.
- Teste a composição da URL em `Settings`.
- Teste que o adapter usa `_run_on_browser_thread`.
- Teste seleção por rótulo e a ordem modalidade -> tipo de concurso.
- Teste que `Aplicar` é clicado uma única vez quando há filtros.
- Teste que o botão não é clicado desnecessariamente quando não há filtros e os padrões já estão ativos.
- Teste que filtros omitidos não reaproveitam estado anterior.
- Teste tabela vazia.
- Teste parsing de Mega-Sena.
- Teste parsing de Super Sete sem incluir os cabeçalhos das colunas.
- Teste normalização de situação.
- Teste parsing de data/hora com timezone de São Paulo.
- Teste linha malformada.
- Teste redirecionamento inesperado.

Use fakes de `Page`, `Locator` ou objetos equivalentes. Nenhum teste deve depender do portal ou de uma instalação local do Chromium.

## Testes de Integração da API

Atualize `tests/integration/test_api_routes.py`:

- `FakeContainer` deve expor `list_portal_bets`.
- OpenAPI deve conter o método `GET` em `/api/v1/bets` e preservar o método `POST` em `/api/v1/bets/run`.
- OpenAPI deve documentar os parâmetros e respostas esperadas.
- `GET /api/v1/bets` deve retornar a lista serializada.
- A data deve ser serializada com `-03:00` e sem microssegundos.
- Uma lista vazia deve retornar `200` e `[]`.
- Todos os query parameters devem chegar ao caso de uso.
- Um `month_year` pertencente à janela móvel deve chegar ao caso de uso e retornar `200`.
- Um `month_year` fora da janela móvel deve retornar o envelope padronizado `400`.
- Filtro inválido deve retornar o envelope padronizado `400`.
- Sessão fechada deve retornar o envelope padronizado `409`.
- Falha de redirecionamento deve retornar o envelope padronizado `502`.
- `GET /api/v1/history/bets` deve continuar consultando o fake do histórico, não o fake do portal.
- `POST /api/v1/bets/run` deve permanecer funcional.

Os testes não devem acessar `ONLINE_LOTTERY_URL`, MongoDB ou serviços externos.

## Testes de Arquitetura e Cobertura

- Preserve todas as regras de `tests/unit/test_architecture.py`.
- `application` não pode importar Playwright, FastAPI ou `infrastructure`.
- `api` não pode importar Playwright.
- O novo código deve manter 100% de cobertura conforme `pyproject.toml`.
- Não exclua novos arquivos da cobertura apenas para fazer a suíte passar.

## Documentação

Atualize:

- `README.md` com o novo endpoint, parâmetros, valores canônicos, os nomes públicos específicos de `lottery_modality`, a janela móvel de `month_year`, a pré-condição da sessão e um exemplo de resposta.
- `ARCHITECTURE.md` com o fluxo API -> caso de uso -> porta -> adapter Playwright.
- `DEVELOPMENT.md` apenas se necessário para registrar novas convenções de filtros ou testes.
- `.env.example` com `PORTAL_BETS_PATH=/apostas`.

Deixe explícita a diferença:

- `/api/v1/bets`: consulta ao vivo na sessão autenticada do portal.
- `/api/v1/history/bets`: consulta a apostas persistidas no MongoDB.

## Critérios de Aceite

A entrega está correta quando:

- `GET /api/v1/bets` existe e consulta o portal pela porta de aplicação.
- Os seis filtros opcionais funcionam isolados ou combinados.
- Valores canônicos dos demais filtros são convertidos nos rótulos corretos.
- `lottery_modality` reutiliza `LotteryModality` e aceita somente `Todas`, `Dia de Sorte`, `Dupla Sena`, `Loteca`, `Lotofácil`, `Lotomania`, `+Milionária`, `Mega-Sena`, `Quina`, `Super Sete` e `Timemania`.
- `LotteryModalityBuilder.get_lottery_modality` permanece inalterado.
- O mapper específico do filtro preserva exatamente capitalização, acentuação e espaçamento.
- Rótulos portugueses dos demais filtros são aceitos como aliases.
- `month_year` aceita os períodos relativos e somente o mês corrente mais os cinco meses anteriores.
- A janela de `month_year` avança automaticamente a cada mudança de mês e funciona na virada do ano.
- A validação de `month_year` usa a data corrente em `America/Sao_Paulo` por meio de relógio injetável.
- Os meses de calendário não estão congelados em enum ou lista fixa.
- Valores inválidos retornam `400` antes de qualquer interação Playwright.
- Sessão fechada retorna `409`.
- Após sucesso, a sessão continua aberta e não permanece com status `RUNNING`.
- A URL é derivada de `Settings`.
- Seletores ficam centralizados na infraestrutura.
- Opções são selecionadas por rótulo, não por valores internos do Angular.
- O botão `Aplicar` é acionado no máximo uma vez por consulta.
- Requisições sucessivas não vazam filtros entre si.
- A tabela é aguardada após a aplicação dos filtros.
- Data e hora são combinadas em `purchase_datetime` com timezone de São Paulo.
- Modalidade, números, concurso e situação são extraídos corretamente.
- Mega-Sena e Super Sete são cobertas por testes de parsing.
- Pesquisa sem resultados retorna `[]`.
- A consulta não persiste dados e não acessa `BetRepositoryPort`.
- `POST /api/v1/bets/run` permanece funcional.
- Os endpoints de histórico permanecem funcionais.
- O OpenAPI documenta a nova operação e seus erros.
- As regras de arquitetura continuam passando.
- A suíte mantém 100% de cobertura.
- Nenhum teste abre Chromium ou acessa o portal real.

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

## Observações de Segurança e Escopo

- Não grave CPF, senha, CVV, dados de cartão, tokens, cookies ou códigos reais no código, nos testes, nos logs ou na documentação.
- Não exponha o perfil persistente do Chromium.
- Não registre o HTML completo de páginas autenticadas.
- Não tente burlar CAPTCHA, bloqueios, autenticação ou controles do portal.
- A nova rota é somente de consulta: não deve apostar, adicionar itens ao carrinho, confirmar compra ou confirmar pagamento.
- Preserve `CONFIRM_PAYMENT=false` e `MONGODB_ENABLED=false` como padrões seguros.
- Não adicione dependências novas sem necessidade comprovada.
