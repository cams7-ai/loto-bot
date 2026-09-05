# Prompt para Codex GPT-5.5: Conferência e Notificação de Resultados das Apostas

Você é um engenheiro de software sênior especializado em Python 3.12, FastAPI, Clean Architecture, SOLID, Playwright, integração com serviços externos e testes automatizados.

A sua missão é evoluir o projeto **LotoBot** para criar o endpoint:

```http
POST /api/v1/bets/check_draws
```

Esse endpoint deve consultar as apostas persistidas no histórico, buscar as apostas correspondentes no portal Loterias Online CAIXA, correlacionar os resultados e enviar uma única notificação consolidada pelo WhatsApp. Quando não for possível enviar pelo WhatsApp, deve enviar a mesma informação por e-mail como fallback. Nenhuma notificação deve ser enviada quando nenhuma aposta correspondente for encontrada.

Antes de alterar qualquer arquivo, leia o código atual, os testes, os prompts mais recentes em `prompts/`, `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md` e `pyproject.toml`. Preserve mudanças locais do usuário e adapte a implementação ao estado real do repositório.

Toda lógica interna do código deve continuar em inglês, incluindo nomes de classes, funções, métodos, módulos, variáveis e objetos de domínio. Comentários no código, mensagens de erro, logs personalizados, documentação técnica, README e textos direcionados ao usuário ou mantenedor devem estar em português do Brasil.

Ajuste o código atual para evitar duplicidade de código. Sempre que a nova funcionalidade revelar regras, validações, normalizações, mapeamentos, builders ou fluxos repetidos, refatore-os para uma única fonte de verdade reutilizável, preservando os contratos e comportamentos existentes. Não copie implementações apenas para atender ao novo endpoint.

## Contexto Atual

O projeto já possui os endpoints:

```http
GET /api/v1/history/bets
GET /api/v1/bets
```

O endpoint `GET /api/v1/history/bets` consulta as apostas persistidas no MongoDB por meio de `ListPlacedBetsUseCase`. Seus filtros incluem:

- `lottery_modality`;
- `draw_number`;
- `start_date`;
- `end_date`.

O endpoint `GET /api/v1/bets` consulta as apostas exibidas no portal Loterias Online CAIXA por meio de `ListPortalBetsUseCase`. Seus filtros incluem:

- `bet_type`;
- `lottery_modality`;
- `draw_type`;
- `month_year`;
- `status`;
- `sort_by`.

O projeto também já possui:

- `NotificationPort`;
- `NotificationGateway`;
- `WhatsAppNotifyClient`;
- `MailSenderClient`;
- builders de mensagens de notificação;
- validação estruturada de filtros com `ValidationErrorDetail`;
- tratamento padronizado de `ApiError`;
- timezone `America/Sao_Paulo`;
- injeção de dependências por `AppContainer`.

Atualmente, a validação dos filtros das duas consultas acontece em `BetRequestParser`, antes da chamada aos casos de uso. `parse_placed_bet_filters` produz um `BetSearchFilters` e `parse_portal_bet_filters` produz um `PortalBetSearchFilters`; `ListPlacedBetsUseCase.run` e `ListPortalBetsUseCase.run` recebem esses objetos tipados e não recebem os parâmetros brutos da API.

### Estado atual após os últimos ajustes

Considere os contratos abaixo como parte do estado atual e não os reverta durante a implementação:

- `main.py` é apenas o wrapper local; `src/main.py` carrega `.env`, configura o logging e inicia `api.server:app` com Uvicorn.
- `SessionStatusResult` usa `UUID` e `AutomationStatus`, e `AutomationRunResult` também usa `UUID` e `AutomationStatus`.
- Os valores públicos atuais de `AutomationStatus` estão em português: `Fechada`, `Aberta`, `Em execução`, `Falhou` e `Finalizada`.
- `PortalBetResult.purchase_datetime` é um `datetime` obrigatório. `PortalBetResult.lottery_modality` é `LotteryModality | str`, permitindo preservar uma modalidade desconhecida do portal sem perder as modalidades reconhecidas.
- `PlacedBetResult.lottery_modality`, `bet_amount` e `bet_date` são obrigatórios.
- O adapter `PortalBetsBrowserMixin` é responsável por produzir a data da compra com timezone de São Paulo e sem microssegundos, além de converter modalidades reconhecidas para o nome canônico do enum, como `MEGA_SENA`. Rótulos desconhecidos são preservados. Há, porém, uma correção necessária em `_purchase_datetime_with_timezone`: `parse_sao_paulo_datetime` já retorna um `datetime` com `America/Sao_Paulo`, e a sequência atual `astimezone(UTC).replace(tzinfo=sao_paulo_timezone())` desloca indevidamente o horário de parede em três horas. Corrija isso sem transferir a normalização para o mapper ou para o novo caso de uso.
- O catálogo público aceita todos os membros de `LotteryModality`, mas `PortalLotteryModalityBuilder` ainda não possui mapeamento para `QUINA_ESPECIAL`, `LOTECA_ESPECIAL` e `LOTOFACIL_ESPECIAL`. A normalização reversa de `PortalBetsBrowserMixin` também não reconhece todos os rótulos conhecidos do portal, como `+Milionária` e os nomes especiais fornecidos por `LotteryModalityBuilder`. Complete e centralize esse mapeamento para que todo valor aceito seja selecionável e volte ao nome canônico correto, sem transformar um `KeyError` em `500`. Continue preservando literalmente somente rótulos realmente desconhecidos.
- `BetModel.to_result()` é responsável por quantizar `bet_amount` para duas casas e normalizar `bet_date` para `America/Sao_Paulo`, sem microssegundos. `ApiResponseMapper` apenas converte os DTOs tipados para os schemas de resposta.
- `ApiResponseMapper` possui métodos separados para controle e consulta de status da sessão. Novos resultados devem receber um mapper específico, sem adicionar condicionais genéricas aos métodos existentes.
- Os schemas de resposta são enxutos. Exemplos de sucesso e erros do OpenAPI ficam nas constantes `responses` das rotas, usando `success_response` e `error_response`.
- `ApiExceptionMapper.raise_invalid_parameters` recebe a exceção `PortalBetFiltersValidationError` completa e preserva o encadeamento com `raise ... from exc`.
- O OpenAPI remove as respostas automáticas `422`; erros de validação públicos devem continuar sendo apresentados como `400` no formato padronizado do projeto.
- No baseline revisado, `python -m pytest` executa 116 testes com sucesso, `ruff check` passa e 107 arquivos estão formatados. Entretanto, `python -m pytest --cov=src --cov-report=term-missing` mede 83,10% e falha porque `pyproject.toml` configura `fail_under = 100`. Portanto, 100% é uma meta ainda não atendida pelo estado atual, não uma garantia a ser apenas “mantida”. Não reduza o limite nem omita essa dívida na entrega.

Reutilize essas estruturas e evolua seus contratos somente quando necessário. Não faça requisições HTTP internas para os endpoints existentes. A composição deve ocorrer entre casos de uso e portas da camada `application`.

Arquivos relevantes incluem, sem se limitar a:

- `src/main.py`;
- `src/api/routes/bets.py`;
- `src/api/schemas/automation_schema.py`;
- `src/api/parsers/bet_request_parser.py`;
- `src/api/mappers/api_response_mapper.py`;
- `src/api/responses.py`;
- `src/api/dependencies.py`;
- `src/application/dto/automation_dto.py`;
- `src/application/use_cases/list_placed_bets.py`;
- `src/application/use_cases/list_portal_bets.py`;
- `src/application/ports/notification_port.py`;
- `src/application/notification/notification_message_builder.py`;
- `src/application/services/portal_bet_filter_catalog.py`;
- `src/domain/entities/automation_session.py`;
- `src/infrastructure/browser/portal_bets_browser.py`;
- `src/infrastructure/clients/notification_gateway.py`;
- `src/infrastructure/database/models/bet_model.py`;
- `src/infrastructure/selectors/portal_bet_filter_builder.py`;
- `src/shared/datetime_utils.py`;
- `tests/conftest.py`;
- `tests/integration/test_api_routes.py`;
- testes unitários dos casos de uso, notificações e validações.

## Objetivo

Crie o endpoint:

```http
POST /api/v1/bets/check_draws
```

O endpoint deve receber um JSON no request body com os seguintes atributos obrigatórios:

- `lottery_modality`;
- `start_date`;
- `end_date`.

Também deve aceitar os seguintes atributos opcionais:

- `bet_type`;
- `draw_type`;
- `month_year`;
- `status`.

Exemplo:

```json
{
  "lottery_modality": "MEGA_SENA",
  "start_date": "2026-07-27",
  "end_date": "2026-07-27",
  "bet_type": "INDIVIDUAL",
  "draw_type": "ALL",
  "month_year": "LAST_7_DAYS",
  "status": "ALL"
}
```

Não adicione `sort_by` ao contrato público desse novo endpoint. O `PortalBetSearchFilters` entregue a `ListPortalBetsUseCase` deve usar `sort_by=None`, pois a ordenação não participa da regra de correlação. Isso preserva o comportamento atual do builder do portal, que aplica `DATE_DESC` como seleção padrão quando o campo tipado está ausente.

## Fluxo de Orquestração

Crie um caso de uso específico para a nova operação, por exemplo:

```text
application/use_cases/check_bet_draws.py
```

Um nome sugerido para a classe é `CheckBetDrawsUseCase`. Ajuste o nome apenas se houver uma convenção mais adequada no projeto.

O fluxo deve ser:

1. Validar e converter todos os campos do request antes de acessar o repositório, o portal ou os serviços de notificação.
2. Montar um `BetSearchFilters` e chamar `ListPlacedBetsUseCase.run` uma única vez com esse objeto:
   - `lottery_modality` convertido para `LotteryModality`; quando o valor público for `ALL`, usar `None`, conforme a semântica atual do histórico;
   - `start_date` convertido para o início do dia;
   - `end_date` convertido para `23:59:59`;
   - `draw_number=None`.
3. Se o histórico não retornar nenhuma aposta, encerrar o fluxo com sucesso:
   - não chamar `ListPortalBetsUseCase`;
   - não consultar WhatsApp;
   - não enviar WhatsApp;
   - não enviar e-mail.
4. Montar um `PortalBetSearchFilters` e chamar `ListPortalBetsUseCase.run` uma única vez com esse objeto:
   - `lottery_modality` convertido para `LotteryModality`; `ALL` é representado por `None`, como já ocorre em `parse_portal_lottery_modality`;
   - `bet_type`, `draw_type`, `month_year` e `status` convertidos para seus tipos de domínio;
   - `sort_by=None`;
   - `has_explicit_filters=True`, pois `lottery_modality` é obrigatório e foi explicitamente informado. Essa flag, e não a string `ALL`, preserva para o adapter a distinção entre uma consulta sem filtros explícitos e uma consulta que informou `ALL`.
5. Correlacionar em memória os dados retornados pelo portal com as apostas retornadas pelo histórico.
6. Manter apenas as apostas do portal cuja chave composta corresponda a uma aposta do histórico:
   - `lottery_modality`;
   - `selected_numbers`;
   - `draw_number`.
7. Se não houver nenhuma correspondência após a correlação, encerrar o fluxo com sucesso sem chamar qualquer serviço de notificação.
8. Se houver correspondências, montar uma única mensagem consolidada contendo todas as apostas correspondentes.
9. Tentar enviar essa mensagem pelo WhatsApp.
10. Enviar por e-mail somente quando não for possível concluir o envio pelo WhatsApp.
11. Retornar um resultado que informe a quantidade de apostas correspondentes, se houve notificação e o canal utilizado.

O novo caso de uso deve orquestrar os casos de uso existentes diretamente. Não duplique consultas ao MongoDB, parsing do portal, aplicação de filtros Playwright ou regras de validação já existentes. Entregue ao orquestrador um DTO de entrada tipado que contenha os dois objetos de filtro, ou campos tipados equivalentes; não faça o caso de uso depender de schemas Pydantic da camada `api`.

`ListPortalBetsUseCase` não valida parâmetros brutos: a validação atual ocorre em `BetRequestParser.parse_portal_bet_filters`, antes de `run`. Reutilize ou extraia essa fronteira sem efeitos colaterais para validar o corpo integralmente antes da consulta ao histórico. Faça o mesmo com a semântica de datas de `parse_placed_bet_filters`. O resultado deve ser um contrato tipado entregue ao orquestrador. Não copie catálogos nem mantenha duas implementações divergentes da mesma regra.

Não chame os dois parsers atuais de forma independente e apenas concatene suas falhas: ambos tratam `lottery_modality`, e a ordem nativa do parser do portal começa por `bet_type`. Extraia helpers puros por campo ou crie um parser combinado que reutilize esses helpers, valide `lottery_modality` uma única vez, capture `SaoPauloClock.today()` uma única vez e produza exatamente a ordem de detalhes definida neste prompt.

## Regra de Correlação

Monte uma chave imutável para cada aposta do histórico e do portal:

```text
(lottery_modality, selected_numbers, draw_number)
```

Regras:

- Normalize `lottery_modality` na função que monta a chave, sem alterar os DTOs recebidos: use `LotteryModality.name` para o histórico e o nome canônico já produzido pelo browser para modalidades reconhecidas no portal.
- Uma modalidade desconhecida preservada pelo portal não deve corresponder por aproximação a uma modalidade tipada do histórico.
- Compare `draw_number` pelo valor textual limpo, preservando zeros quando existirem.
- Compare `selected_numbers` como sequência posicional de strings limpas, convertida para `tuple` na chave imutável.
- Preserve zeros à esquerda.
- Não transforme `selected_numbers` em `set`.
- Não reordene os números.
- A ordem pode ser semanticamente relevante para modalidades como Super Sete e formatos não numéricos.
- Não use `purchase_datetime`, `bet_id`, `purchase_number`, `status` ou `bet_date` para decidir a correspondência.
- Use o conjunto de chaves do histórico para filtrar a lista do portal uma única vez.
- Uma aposta retornada pelo portal deve aparecer no máximo uma vez na mensagem, mesmo que o histórico contenha registros duplicados com a mesma chave.
- Preserve na mensagem a ordem em que as apostas foram retornadas por `ListPortalBetsUseCase`.

O `status` persistido no histórico, por exemplo `"Efetivada"`, não participa da correlação. A situação apresentada na mensagem deve ser o `status` atual retornado pelo portal, por exemplo `"Concurso não apurado"` ou `"Aposta não premiada"`.

## Contrato do Request

Crie um schema específico, por exemplo `CheckBetDrawsRequest`.

### Campos obrigatórios

#### `lottery_modality`

- Deve reutilizar a mesma fonte de verdade e a mesma normalização já usadas pelos endpoints de histórico e portal.
- Deve aceitar os nomes de `LotteryModality` e `ALL`, exatamente como os endpoints de consulta atuais; não aceite os valores internos em kebab-case como contrato alternativo.
- Deve ser convertido para `LotteryModality | None` antes de chamar o fluxo de histórico, com `ALL` representado por `None`.
- No `PortalBetSearchFilters`, use a mesma conversão: uma modalidade concreta vira `LotteryModality` e `ALL` vira `None`. Preserve a informação de que houve filtro explícito com `has_explicit_filters=True`; `ListPortalBetsUseCase.run` não aceita a string pública `ALL`.
- Não mantenha listas duplicadas de valores permitidos na rota, schema, caso de uso e testes.
- Garanta que cada modalidade aceita tenha mapeamento de ida para o rótulo do filtro do portal e de volta para o nome canônico observado nas linhas. Reutilize uma única fonte de aliases para nomes como `+Milionária`, `Quina de São João`, `Loteca Especial` e `Lotofácil da Independência`.

#### `start_date` e `end_date`

- Devem usar o formato `YYYY-MM-DD`.
- `start_date` deve ser convertido para o início do dia.
- `end_date` deve ser convertido para `23:59:59`, seguindo exatamente a semântica atual de `BetRequestParser.parse_placed_bet_filters` e de `GET /api/v1/history/bets`.
- `start_date` não pode ser posterior a `end_date`.
- Não introduza uma conversão exclusiva desse endpoint: reutilize a mesma representação `datetime` atualmente entregue ao `ListPlacedBetsUseCase`.

### Campos opcionais

#### `bet_type`

Reutilize os nomes canônicos e a validação de `PortalBetType`.

#### `draw_type`

Reutilize os nomes canônicos e a validação de `PortalDrawType`.

#### `month_year`

Reutilize `parse_portal_month_year` e a mesma data de referência em São Paulo usada por `BetRequestParser.parse_portal_bet_filters`, incluindo os períodos relativos e a janela do mês atual e dos cinco anteriores. Preserve também a aceitação atual do rótulo localizado `Mês/YYYY`; o formato público canônico nos exemplos e em `allowed_values` continua sendo `YYYY-MM`.

#### `status`

Reutilize os nomes canônicos e a validação de `PortalBetStatus`.

Os campos opcionais omitidos devem resultar em `None` no `PortalBetSearchFilters`, preservando o comportamento atual do builder: `ALL` para tipo, modalidade, concurso e situação, `LAST_7_DAYS` para período e `DATE_DESC` para ordenação.

Não declare simplesmente os três campos obrigatórios como `str` sem default, pois isso faz o Pydantic interromper a requisição antes da validação acumulada. Modele a entrada de forma que a API consiga receber os valores brutos, inclusive ausência, `null` e tipos JSON diferentes de string, e então produza todos os detalhes em uma única passagem. O OpenAPI ainda deve marcar `lottery_modality`, `start_date` e `end_date` como obrigatórios; se o modelo precisar de defaults técnicos para permitir o parsing manual, ajuste o schema gerado de forma explícita e teste a lista `required`.

## Validação

Valide o corpo integralmente antes de executar qualquer efeito externo.

Quando houver mais de um campo inválido, acumule os detalhes na ordem:

1. `lottery_modality`;
2. `start_date`;
3. `end_date`;
4. `bet_type`;
5. `draw_type`;
6. `month_year`;
7. `status`.

Reutilize o contrato estruturado introduzido no projeto:

```json
{
  "error": {
    "timestamp": "2026-07-28T22:00:00-03:00",
    "status_code": 400,
    "code": "REQUISICAO_INVALIDA",
    "message": "Campos inválidos",
    "details": [
      {
        "field": "lottery_modality",
        "rejected_value": "abc",
        "allowed_values": [
          "ALL",
          "MEGA_SENA",
          "QUINA"
        ],
        "message": "Valor inválido."
      },
      {
        "field": "start_date",
        "rejected_value": "abc",
        "message": "Valor inválido. Utilize o formato YYYY-MM-DD."
      }
    ]
  }
}
```

A lista de `allowed_values` acima está abreviada apenas para legibilidade. Na implementação e no OpenAPI, use a lista completa fornecida pela fonte de verdade atual do projeto.

Regras adicionais:

- Campo obrigatório ausente deve produzir detalhe com `field`, `rejected_value: null` e `message: "Campo obrigatório."`.
- Valor `null`, vazio ou contendo somente espaços em campo obrigatório deve produzir o mesmo detalhe de campo obrigatório.
- Valor de tipo JSON diferente de string deve ser rejeitado pelo parser manual, preservado sem coerção em `rejected_value` e não deve cair no handler genérico de `RequestValidationError`.
- Preserve em `rejected_value` o valor original recebido.
- Evolua `ValidationErrorDetail.rejected_value` de `str` para `object | None` ou outro tipo amplo equivalente, de forma compatível com os usos existentes. Não transforme `null` em string vazia nem converta números e booleanos para texto apenas para montar o erro.
- Datas impossíveis, como `2026-02-30`, devem ser rejeitadas.
- Se `start_date` for posterior a `end_date`, associe o detalhe a `start_date` e use a mensagem já adotada pelo projeto para essa relação.
- Erros dos campos opcionais devem ter os mesmos `allowed_values` e mensagens usados por `GET /api/v1/bets`.
- Nenhum filtro inválido pode chegar ao repositório ou ao portal.
- Não exponha `error.fields` nem `error.messages` nesse fluxo.

Não dependa da interrupção automática do Pydantic/FastAPI para os sete campos desse body. O handler global de `RequestValidationError` hoje retorna apenas `"Corpo da requisição inválido."`, e o OpenAPI remove o `422`; portanto, centralize a conversão em uma fronteira reutilizável da aplicação ou em helpers de API coerentes com o código atual, sem importar FastAPI na camada `application`. Reutilize `ApiExceptionMapper.raise_invalid_fields` para produzir `message: "Campos inválidos"`, ou evolua essa fronteira sem alterar o contrato dos endpoints existentes.

## Mensagem de Notificação

Crie builders específicos para o resultado da conferência, mantendo a montagem das mensagens fora da infraestrutura.

Deve ser montada uma única mensagem com todas as apostas correspondentes. Cada aposta deve conter obrigatoriamente os valores retornados pelo caso de uso do portal:

- `purchase_datetime`;
- `lottery_modality`;
- `selected_numbers`;
- `draw_number`;
- `status`.

Exemplo de conteúdo para WhatsApp:

```text
Resultado da conferência de apostas

Data/hora da compra: 27/07/2026 23:14:44
Modalidade: MEGA_SENA
Números selecionados: 02, 20, 28, 48, 57, 59
Concurso: 3037
Situação: Concurso não apurado
```

Quando houver mais de uma aposta, repita o bloco e separe os itens de forma legível. Não envie uma mensagem por aposta.

Regras de formatação:

- Formate `purchase_datetime` em `dd/MM/yyyy HH:mm:ss`, no timezone `America/Sao_Paulo`.
- Considere `purchase_datetime` obrigatório. Não reintroduza `None` no DTO nem um fallback `-`; uma linha sem data válida deve continuar sendo rejeitada pelo parser do portal.
- Corrija a normalização do browser para que um texto `27/07/2026 23:14:44` lido no portal resulte em `2026-07-27T23:14:44-03:00`, sem deslocamento do horário de parede e sem microssegundos. Reutilize `with_sao_paulo_timezone(..., remove_microseconds=True)` ou comportamento equivalente; não use `replace(tzinfo=...)` depois de converter para UTC.
- Normalize todos os rótulos conhecidos do portal para `LotteryModality.name` antes da correlação. Rótulos fora do catálogo continuam como `str` original e não devem corresponder por aproximação.
- Preserve acentos, zeros à esquerda e a ordem de `selected_numbers`.
- Use texto simples apropriado para WhatsApp.
- Para e-mail, crie uma versão HTML equivalente e semanticamente legível.
- Escape dados externos antes de inseri-los no HTML.
- Use um assunto explícito, por exemplo `LotoBot - resultado da conferência de apostas`.
- Não inclua no texto campos vindos apenas do histórico quando eles não fizerem parte do resultado do portal.
- Não registre o corpo completo da notificação em log.

## WhatsApp e Fallback para E-mail

Evolua `NotificationPort` e `NotificationGateway` com uma operação específica ou uma abstração genérica coerente que permita enviar a notificação da conferência e informar o canal efetivamente usado.

Atualmente, `notify_success` sempre tenta enviar e-mail depois da tentativa de WhatsApp e `notify_failure` devolve apenas um booleano. Nenhum desses contratos representa a semântica deste endpoint. Crie uma operação nova, com retorno tipado do canal utilizado, e mantenha os dois métodos existentes sem alteração comportamental.

O comportamento obrigatório é:

1. Se o WhatsApp estiver habilitado e sua sessão estiver aberta, tentar enviar a mensagem.
2. Se o WhatsApp confirmar o status de mensagem enviada, considerar o fluxo concluído e não enviar e-mail.
3. Se o WhatsApp estiver desabilitado, usar e-mail.
4. Se a sessão do WhatsApp não estiver aberta, usar e-mail.
5. Se a consulta de status do WhatsApp falhar, usar e-mail.
6. Se o envio do WhatsApp lançar erro, usar e-mail.
7. Se o WhatsApp retornar qualquer status diferente de enviado, usar e-mail.
8. Se o e-mail de fallback for enviado, informar que o canal utilizado foi `EMAIL`.
9. Se os dois canais falharem, propagar um erro tipado de serviço externo e mapear a resposta conforme o padrão atual da API; não retorne sucesso falso.

Use os valores atuais `WhatsAppSessionStatus.SESSION_OPEN.value` (`SESSAO_ABERTA`) e `WhatsAppMessageStatus.SENT.value` (`enviado`) como fonte de verdade. Quando o WhatsApp estiver desabilitado, não consulte seu status; vá diretamente para o e-mail.

Para esta operação, considere o WhatsApp disponível somente quando `session.whatsapp_enabled` for verdadeiro. Esse atributo é definido por `NotificationGateway.start_whatsapp_session` durante a abertura da sessão; se a integração estiver desabilitada ou sua inicialização tiver falhado, ele permanece falso e o novo método deve ir diretamente ao e-mail. Use uma nova `Operation.CHECK_BET_DRAWS` em todas as chamadas aos clients e nos erros dessa etapa, sem reutilizar acidentalmente `Operation.LIST_PORTAL_BETS` deixada pela consulta anterior.

Não reutilize `notify_success` se ele continuar enviando e-mail mesmo depois de um WhatsApp bem-sucedido. Preserve o comportamento dos fluxos existentes e crie uma operação adequada à semântica exclusiva de fallback deste endpoint.

Não inicie nem encerre automaticamente a sessão persistente do navegador ou do WhatsApp no novo caso de uso. A consulta ao portal deve continuar respeitando a pré-condição atual de sessão aberta de `ListPortalBetsUseCase`.

## Contrato da Resposta

Crie um schema específico, por exemplo `CheckBetDrawsResponse`, com:

- `matched_bets`: inteiro não negativo com a quantidade de apostas do portal que corresponderam ao histórico;
- `notification_sent`: booleano;
- `notification_channel`: `WHATSAPP`, `EMAIL` ou `NONE`;
- `message`: descrição curta em português.

Mantenha a invariância do resultado: `notification_sent` é `false` se, e somente se, `notification_channel` for `NONE`. Como uma falha dos dois canais gera erro, toda resposta de sucesso com `matched_bets > 0` deve informar `notification_sent=true` e canal `WHATSAPP` ou `EMAIL`.

Exemplo com envio pelo WhatsApp:

```json
{
  "matched_bets": 1,
  "notification_sent": true,
  "notification_channel": "WHATSAPP",
  "message": "Conferência concluída e notificação enviada pelo WhatsApp."
}
```

Exemplo sem apostas no histórico ou sem correspondências:

```json
{
  "matched_bets": 0,
  "notification_sent": false,
  "notification_channel": "NONE",
  "message": "Conferência concluída. Nenhuma aposta correspondente foi encontrada."
}
```

Quando houver apostas correspondentes e o WhatsApp falhar, mas o e-mail for enviado:

```json
{
  "matched_bets": 1,
  "notification_sent": true,
  "notification_channel": "EMAIL",
  "message": "Conferência concluída e notificação enviada por e-mail."
}
```

Use status HTTP `200` para a conclusão com ou sem correspondências. Reutilize os erros padronizados já aplicáveis a validação, sessão fechada, automação, redirecionamento e indisponibilidade de serviços externos. Documente no OpenAPI pelo menos os status `200`, `400`, `409`, `500`, `502` e `503`, desde que coerentes com os mappers atuais.

Siga o padrão atual das rotas: mantenha `CheckBetDrawsResponse` apenas com os campos tipados e declare exemplos de sucesso em uma constante como `CHECK_BET_DRAWS_RESPONSES`, composta com `success_response` e `error_response`. Inclua exemplos distintos de WhatsApp, e-mail e nenhuma correspondência na documentação da rota, sem recolocar exemplos de resposta em `json_schema_extra`.

O helper `success_response` atual aceita um único `example`. Se forem necessários múltiplos exemplos nomeados para o mesmo status `200`, evolua esse helper de forma retrocompatível para aceitar `examples`, ou componha o `content` na constante da rota mantendo `Utf8JSONResponse.media_type`. Não quebre as respostas documentadas dos endpoints existentes.

## Ajustes Esperados por Camada

### Camada `domain`

- Adicione `Operation.CHECK_BET_DRAWS`, com valor público em português, para identificar a correlação e a notificação nos logs e erros tipados.
- Preserve os valores em português de `AutomationStatus`; a nova operação não deve criar estados paralelos como strings literais.
- Modele `WHATSAPP`, `EMAIL` e `NONE` em um enum tipado. Coloque-o em `domain` somente se o canal representar um conceito estável compartilhado; caso contrário, mantenha-o em `application`.
- Não importe FastAPI, Pydantic, Playwright, Beanie, Motor ou clients HTTP.

### Camada `application`

- Crie o caso de uso orquestrador da conferência.
- Crie DTOs tipados de entrada e resultado para deixar explícitos os dois conjuntos de filtros e o contrato retornado, sem transportar schemas Pydantic para a aplicação.
- Reutilize `ListPlacedBetsUseCase` e `ListPortalBetsUseCase`.
- Não acesse repositório, navegador ou clients concretos diretamente.
- Evolua `NotificationPort` sem quebrar os casos de uso existentes.
- Crie builders de mensagem testáveis e determinísticos.
- Mantenha a correlação em uma função pequena e testável.
- Consuma `PlacedBetResult` e `PortalBetResult` já normalizados pelas fronteiras de infraestrutura; não mova normalização de moeda, timezone ou parsing do portal para o novo caso de uso.
- Exporte os novos tipos pelos respectivos `__init__.py`.

### Camada `infrastructure`

- Implemente no `NotificationGateway` o envio WhatsApp com fallback exclusivo para e-mail.
- Reutilize `WhatsAppNotifyClient` e `MailSenderClient`.
- Não replique chamadas HTTP dos clients.
- Preserve os logs com `Operation.executed_operation`.
- Preserve a responsabilidade de normalização em `PortalBetsBrowserMixin` e `BetModel.to_result()`, mas corrija em `PortalBetsBrowserMixin` o deslocamento indevido do horário já descrito. `BetModel.to_result()` deve permanecer responsável pela quantização e pelo timezone dos registros persistidos.
- Complete o mapeamento de `PortalLotteryModalityBuilder` e compartilhe os aliases conhecidos com a normalização de `PortalBetsBrowserMixin`, evitando catálogos divergentes entre seleção e leitura.
- Não engula a falha final quando WhatsApp e e-mail falharem.

### Camada `api`

- Adicione `CheckBetDrawsRequest` e `CheckBetDrawsResponse`.
- Adicione a rota `POST /api/v1/bets/check_draws`.
- Converta o request para o contrato do caso de uso.
- Converta o resultado para o response schema.
- Adicione um método dedicado no `ApiResponseMapper` para o novo resultado, seguindo a separação atual entre os mappers de resposta.
- Reutilize `ApiExceptionMapper`, `ApiError`, `error_response` e o padrão de erro estruturado.
- Registre o novo caso de uso em `AppContainer` e `build_container`.
- Atualize os fakes do container usados nos testes.
- Documente o exemplo de request no schema de entrada quando apropriado e os exemplos de resposta nas constantes `responses` da rota: sucesso por WhatsApp, fallback por e-mail e ausência de correspondências.

## Concorrência e Ciclo de Vida

O endpoint usa a mesma sessão persistente do portal utilizada por `GET /api/v1/bets`.

- Preserve a proteção de thread e o ciclo de vida já implementados no adapter Playwright.
- Não crie outro browser ou outra página.
- Não contorne `_run_on_browser_thread`.
- Não deixe `AutomationSession` presa no estado `RUNNING`.
- Após uma consulta bem-sucedida, preserve o comportamento atual de `ListPortalBetsUseCase`: `mark_running(Operation.LIST_PORTAL_BETS)` antes da consulta e `mark_ready()` ao concluir, restaurando `AutomationStatus.OPEN`, cujo valor público é `Aberta`.
- Quando houver correspondências, marque a sessão como `RUNNING` com `Operation.CHECK_BET_DRAWS` durante a montagem e o envio da notificação. Em sucesso, chame `mark_ready()`; se a notificação final falhar, marque `FAILED` com essa mesma operação e propague a exceção. Não use `SessionFailureHandler`, pois ele tentaria uma segunda notificação operacional e poderia fechar recursos fora da semântica deste endpoint.
- Se o histórico estiver vazio, não consulte nem valide o estado do browser: retorne sucesso preservando o estado atual da sessão. Se houver histórico, a chamada a `ListPortalBetsUseCase` mantém a pré-condição existente e retorna `409` quando o browser estiver fechado.
- Não altere diretamente atributos privados da sessão.
- Não feche a sessão após a conferência.

## Testes Obrigatórios

Crie ou atualize testes unitários cobrindo:

- validação e conversão dos campos obrigatórios;
- `lottery_modality=ALL` vira `None` nos dois objetos tipados de filtro, e o filtro do portal mantém `has_explicit_filters=True`;
- validação dos quatro campos opcionais;
- acumulação de múltiplos erros na ordem definida;
- campo obrigatório ausente, `null`, vazio e somente com espaços;
- data inválida e `start_date` posterior a `end_date`;
- nenhuma dependência é chamada quando o request é inválido;
- `ListPlacedBetsUseCase` recebe `lottery_modality`, início do dia, fim do dia e `draw_number=None`;
- histórico vazio retorna resultado com canal `NONE`;
- o caso de uso do portal não é chamado quando o histórico está vazio;
- `ListPortalBetsUseCase` recebe um `PortalBetSearchFilters` com a modalidade e os quatro filtros opcionais tipados, `sort_by=None` e `has_explicit_filters=True`;
- `ListPortalBetsUseCase` é chamado uma única vez;
- correlação positiva pela chave composta;
- modalidade diferente não corresponde;
- modalidade desconhecida preservada pelo portal não corresponde a uma modalidade tipada do histórico;
- todas as modalidades públicas aceitas, inclusive `MAIS_MILIONARIA`, `QUINA_ESPECIAL`, `LOTECA_ESPECIAL` e `LOTOFACIL_ESPECIAL`, possuem mapeamento de filtro e normalização reversa sem `KeyError`;
- números diferentes não correspondem;
- ordem diferente dos números não corresponde;
- concurso diferente não corresponde;
- zeros à esquerda são preservados;
- status do histórico não participa da correlação;
- duplicidade da mesma chave no histórico não duplica o resultado do portal;
- ordem dos resultados do portal é preservada;
- nenhum match retorna canal `NONE` e não chama o notifier;
- múltiplos matches produzem uma única chamada de notificação;
- a mensagem inclui os cinco campos obrigatórios de cada resultado do portal;
- formatação de data em São Paulo;
- o browser preserva exatamente o horário de parede lido no portal, adiciona `America/Sao_Paulo` e remove microssegundos, sem deslocar três horas;
- `purchase_datetime` permanece obrigatório, timezone-aware e sem microssegundos nos resultados reais do browser;
- e-mail HTML escapa conteúdo externo;
- WhatsApp bem-sucedido não envia e-mail;
- WhatsApp desabilitado envia e-mail;
- sessão do WhatsApp fechada envia e-mail;
- falha ao consultar status do WhatsApp envia e-mail;
- erro ou status não enviado no WhatsApp envia e-mail;
- falha dos dois canais gera erro tipado;
- sucesso da notificação restaura a sessão para `AutomationStatus.OPEN`, falha final a marca como `FAILED` com `Operation.CHECK_BET_DRAWS` e nenhum caminho a deixa em `RUNNING`;
- os fluxos antigos de notificação continuam com o comportamento anterior.

Crie ou atualize testes de integração da API cobrindo:

- OpenAPI contém `POST /api/v1/bets/check_draws`;
- o request body marca `lottery_modality`, `start_date` e `end_date` como obrigatórios;
- os quatro filtros adicionais permanecem opcionais;
- request válido retorna `200` com `matched_bets`, `notification_sent`, `notification_channel` e `message`;
- ausência de apostas retorna `200`, `matched_bets=0`, `notification_sent=false` e `notification_channel="NONE"`;
- request inválido retorna `400` no contrato estruturado;
- campos obrigatórios ausentes, `null` ou de tipo não textual também retornam o `400` estruturado, com `rejected_value` sem coerção;
- os parâmetros são encaminhados corretamente ao novo caso de uso;
- sessão fechada e erros de automação continuam sendo mapeados;
- falha final de notificação é mapeada para erro de serviço externo;
- os endpoints existentes mantêm seus contratos;
- os exemplos de resposta do novo endpoint ficam nas respostas documentadas da rota, não duplicados nos schemas;
- fakes de sessão e execução continuam usando `UUID` e `AutomationStatus`, com os valores públicos em português;
- as regras de arquitetura continuam passando;
- a cobertura total alcança os 100% exigidos por `pyproject.toml`, inclusive fechando as lacunas preexistentes necessárias para que o comando de cobertura termine com sucesso; não reduza `fail_under`.

Todos os testes devem usar fakes ou transports mockados. Não acesse MongoDB real, portal CAIXA real, WhatsApp real ou Mail Sender real.

## Exemplos das APIs Consultadas

### Histórico persistido

```powershell
curl -X GET "http://localhost:8000/api/v1/history/bets?lottery_modality=MEGA_SENA&start_date=2026-07-27&end_date=2026-07-27"
```

```json
[
  {
    "bet_id": "6a67e5db2e00e3a0eebf0e02",
    "lottery_modality": "MEGA_SENA",
    "selected_numbers": [
      "02",
      "20",
      "28",
      "48",
      "57",
      "59"
    ],
    "draw_number": "3037",
    "status": "Efetivada",
    "bet_amount": "6.00",
    "purchase_number": "561353958",
    "bet_date": "2026-07-27T23:14:44-03:00"
  }
]
```

### Apostas no portal

```powershell
curl -X GET "http://localhost:8000/api/v1/bets?bet_type=INDIVIDUAL&lottery_modality=MEGA_SENA&draw_type=ALL&month_year=LAST_7_DAYS&status=ALL&sort_by=DATE_DESC"
```

```json
[
  {
    "purchase_datetime": "2026-07-27T23:14:44-03:00",
    "lottery_modality": "MEGA_SENA",
    "selected_numbers": [
      "02",
      "20",
      "28",
      "48",
      "57",
      "59"
    ],
    "draw_number": "3037",
    "status": "Concurso não apurado"
  },
  {
    "purchase_datetime": "2026-07-26T17:55:01-03:00",
    "lottery_modality": "MEGA_SENA",
    "selected_numbers": [
      "03",
      "20",
      "37",
      "39",
      "47",
      "56"
    ],
    "draw_number": "3037",
    "status": "Concurso não apurado"
  },
  {
    "purchase_datetime": "2026-07-25T02:38:06-03:00",
    "lottery_modality": "MEGA_SENA",
    "selected_numbers": [
      "18",
      "22",
      "32",
      "40",
      "41",
      "46"
    ],
    "draw_number": "3036",
    "status": "Aposta não premiada"
  },
  {
    "purchase_datetime": "2026-07-24T17:23:57-03:00",
    "lottery_modality": "MEGA_SENA",
    "selected_numbers": [
      "01",
      "06",
      "30",
      "32",
      "45",
      "54"
    ],
    "draw_number": "3036",
    "status": "Aposta não premiada"
  }
]
```

Com os exemplos acima, somente a primeira aposta do portal corresponde ao histórico e deve aparecer na notificação.

## Documentação

Atualize `README.md` com:

- objetivo de `POST /api/v1/bets/check_draws`;
- contrato completo do request;
- campos obrigatórios e opcionais;
- exemplo de `curl`;
- respostas com WhatsApp, fallback para e-mail e nenhuma correspondência;
- pré-condição de sessão aberta para consultar o portal;
- erros relevantes;
- regra de correlação;
- garantia de que nenhuma notificação é enviada quando não há correspondências.

Ao revisar os exemplos existentes do README, alinhe `lottery_modality` ao contrato real da API: modalidades reconhecidas são serializadas pelo nome do enum, como `MEGA_SENA`, e não pelo valor interno `mega-sena`. Preserve também os valores atuais em português de `AutomationStatus` nos exemplos de sessão e execução.

Atualize `ARCHITECTURE.md` ou `DEVELOPMENT.md` apenas se a solução introduzir uma convenção arquitetural relevante e duradoura.

## Restrições

- Não faça chamadas HTTP internas para `GET /api/v1/history/bets` ou `GET /api/v1/bets`.
- Não consulte o repositório diretamente pela rota.
- Não consulte o Playwright diretamente pela rota.
- Não envie notificações diretamente pela rota.
- Não duplique a lógica dos casos de uso existentes.
- Não altere o significado dos endpoints existentes.
- Não reverta os valores em português de `AutomationStatus` nem os DTOs tipados com `UUID`, enums e campos obrigatórios.
- Não mova para `ApiResponseMapper` as normalizações que pertencem a `PortalBetsBrowserMixin` e `BetModel.to_result()`; corrija o deslocamento de horário no próprio adapter do portal.
- Não duplique exemplos de resposta em schemas e constantes de rota; siga o padrão atual de `success_response` e `error_response`.
- Não envie e-mail depois de um WhatsApp confirmado como enviado.
- Não envie qualquer notificação quando o histórico estiver vazio ou a correlação não produzir resultados.
- Não adicione dependências sem necessidade.
- Não use `time.sleep`.
- Não reduza cobertura, validações ou tratamento de erros existentes.
- Não faça chamadas reais a serviços externos durante os testes.

## Validação Recomendada

Execute:

```powershell
python -m ruff format --check src tests
python -m ruff check src tests
python -m pytest
python -m pytest --cov=src --cov-report=term-missing
python -m pytest tests/unit/test_architecture.py
```

Se alguma checagem de Ruff falhar, revise a saída antes de executar `ruff format` ou `ruff check --fix`, preserve mudanças locais do usuário e depois execute novamente todas as validações. O comando de cobertura falha no baseline atual com 83,10%; a implementação só satisfaz este prompt quando alcançar o `fail_under = 100` sem excluir código adicional da medição apenas para elevar o percentual.

## Critérios de Aceite

A entrega está correta quando:

- `POST /api/v1/bets/check_draws` existe e está documentado no OpenAPI.
- `lottery_modality`, `start_date` e `end_date` são obrigatórios.
- `lottery_modality=ALL` equivale a `None` nos filtros tipados do histórico e do portal; `has_explicit_filters=True` preserva que o filtro do portal foi informado.
- `bet_type`, `draw_type`, `month_year` e `status` são opcionais.
- O novo endpoint reutiliza `ListPlacedBetsUseCase` e `ListPortalBetsUseCase`, sem HTTP interno.
- Os três campos obrigatórios são usados na consulta do histórico conforme especificado.
- Os filtros opcionais e `lottery_modality` são usados na consulta do portal.
- A consulta ao portal ocorre uma única vez e somente quando o histórico contém apostas.
- A correlação usa exatamente `lottery_modality`, `selected_numbers` na ordem original e `draw_number`.
- Apenas apostas correspondentes do portal entram na mensagem.
- A mensagem contém `purchase_datetime`, `lottery_modality`, `selected_numbers`, `draw_number` e `status`.
- `purchase_datetime` permanece obrigatório e é formatado em `America/Sao_Paulo`, sem criar fallback para valor ausente.
- O horário lido do portal não sofre deslocamento artificial durante a atribuição do timezone de São Paulo.
- Todas as correspondências são agrupadas em uma única notificação.
- WhatsApp é o canal primário.
- E-mail é usado somente como fallback quando o WhatsApp não puder concluir o envio.
- Um WhatsApp bem-sucedido não gera e-mail.
- Se ambos os canais falharem, a API não retorna sucesso falso.
- Nenhuma notificação é tentada quando o histórico estiver vazio.
- Nenhuma notificação é tentada quando não houver correspondências.
- A resposta informa quantidade, envio e canal efetivamente utilizado.
- Entradas inválidas retornam `400` estruturado antes de efeitos externos.
- Os contratos dos endpoints existentes permanecem estáveis.
- README e OpenAPI refletem o comportamento implementado.
- Os exemplos de resposta do OpenAPI seguem o padrão atual das constantes `responses` das rotas.
- Os valores públicos existentes de estado da automação continuam em português.
- A suíte completa, os testes de arquitetura e a cobertura de 100% passam.
