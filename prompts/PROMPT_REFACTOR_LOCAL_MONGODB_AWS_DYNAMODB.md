# Prompt completo — Refatoração de persistência LOCAL MongoDB / AWS DynamoDB

## Contexto do projeto

Repositório:

```text
https://github.com/cams7-ai/loto-bot.git
```

Branch de trabalho:

```text
AWS_FREE_TIER_MIGRATION
```

Projeto:

```text
LotoBot
```

Stack principal:

```text
Python 3.12
FastAPI
Playwright
Beanie
MongoDB
boto3
AWS SAM / CloudFormation
EC2
DynamoDB
pytest
ruff
```

O projeto já possui uma abstração de persistência através de:

```text
BetRepositoryPort
```

e atualmente utiliza:

```text
MongoDatabase
BeanieBetRepository
BetModel
```

para persistência de apostas.

A branch `AWS_FREE_TIER_MIGRATION` já possui a variável:

```text
INTEGRATION_MODE
```

com os valores:

```text
LOCAL
AWS
```

Essa mesma variável deve ser utilizada para decidir qual tecnologia de banco de dados será usada.

---

# Objetivo

Refatorar o LotoBot para utilizar:

```text
INTEGRATION_MODE=LOCAL
        |
        v
MongoDB
        |
        v
BeanieBetRepository
```

e:

```text
INTEGRATION_MODE=AWS
        |
        v
Amazon DynamoDB
        |
        v
DynamoDbBetRepository
```

Não criar uma variável adicional como:

```text
DATABASE_TYPE
DATABASE_MODE
PERSISTENCE_MODE
```

A decisão do banco deve depender exclusivamente de:

```text
INTEGRATION_MODE
```

---

# Regra obrigatória

A seleção do repository deve seguir exatamente a ideia abaixo:

```python
if settings.integration_mode == "AWS":
    bet_repository = DynamoDbBetRepository(...)
else:
    bet_repository = BeanieBetRepository(...)
```

Ou equivalente arquiteturalmente.

Não espalhar verificações de:

```python
if settings.integration_mode == "AWS":
```

pela aplicação.

Essa decisão deve permanecer concentrada no composition root / container de dependências.

Arquivo esperado:

```text
src/api/dependencies.py
```

---

# Arquitetura desejada

A arquitetura final deve ser:

```text
                      Application
                          |
                          v
                  BetRepositoryPort
                          |
             +------------+------------+
             |                         |
             v                         v
   BeanieBetRepository        DynamoDbBetRepository
             |                         |
             v                         v
         MongoDB                  DynamoDB
             ^                         ^
             |                         |
  INTEGRATION_MODE=LOCAL    INTEGRATION_MODE=AWS
```

As camadas:

```text
domain
application
API endpoints
use cases
DTOs
Playwright
```

não devem saber se o banco utilizado é MongoDB ou DynamoDB.

---

# Princípios da refatoração

Seguir estes princípios:

```text
Hexagonal Architecture
Dependency Inversion
Single Responsibility
Open/Closed Principle
baixo acoplamento
mudança mínima no domínio
mudança mínima nos endpoints
```

O contrato:

```text
BetRepositoryPort
```

deve continuar sendo a abstração utilizada pelos casos de uso.

---

# Estado atual relevante

Existe aproximadamente a seguinte estrutura:

```text
src/
├── api/
│   └── dependencies.py
│
├── application/
│   └── ports/
│       └── bet_repository_port.py
│
└── infrastructure/
    └── database/
        ├── connection.py
        ├── models/
        │   └── bet_model.py
        └── repositories/
            └── beanie_bet_repository.py
```

O contrato atual possui operações equivalentes a:

```python
class BetRepositoryPort(Protocol):
    def save(
        self,
        lottery_modality: LotteryModality,
        purchase: PurchaseResult,
    ) -> None:
        ...

    def find_all(
        self,
        filters: BetSearchFilters,
    ) -> list[PlacedBetResult]:
        ...

    def find_by_id(
        self,
        bet_id: str,
    ) -> PlacedBetResult | None:
        ...
```

Esse contrato deve ser preservado sempre que possível.

---

# Refatoração obrigatória

## 1. Manter MongoDB para ambiente LOCAL

Quando:

```text
INTEGRATION_MODE=LOCAL
```

o comportamento atual deve continuar utilizando:

```text
MongoDatabase
BeanieBetRepository
BetModel
MongoDB
```

Não remover suporte ao MongoDB.

Não alterar desnecessariamente:

```text
MongoDatabase
BeanieBetRepository
BetModel
```

A implementação existente deve continuar funcionando localmente.

---

# 2. Criar adapter DynamoDB

Criar:

```text
src/infrastructure/database/repositories/dynamodb_bet_repository.py
```

com uma classe:

```python
class DynamoDbBetRepository(BetRepositoryPort):
    ...
```

Ela deve implementar exatamente:

```text
save
find_all
find_by_id
```

---

# 3. Cliente DynamoDB

Utilizar:

```python
boto3
```

preferencialmente:

```python
boto3.resource("dynamodb")
```

A criação do resource deve ser lazy quando possível.

Exemplo conceitual:

```python
def _table(self):
    if self._table_instance is None:
        if self._resource is None:
            self._resource = boto3.resource("dynamodb")

        self._table_instance = self._resource.Table(
            self._table_name
        )

    return self._table_instance
```

Permitir injeção de um resource fake nos testes.

Exemplo:

```python
DynamoDbBetRepository(
    table_name="loto-bot-bets",
    resource=fake_resource,
)
```

Evitar chamadas reais à AWS durante testes unitários.

---

# 4. Nome da tabela

Adicionar em `Settings`:

```python
dynamodb_table_name: str
```

associado à variável:

```text
DYNAMODB_TABLE_NAME
```

Valor padrão sugerido:

```text
loto-bot-bets
```

No ambiente AWS, o valor deve vir do CloudFormation.

Exemplo:

```text
DYNAMODB_TABLE_NAME=loto-bot-bets
```

---

# 5. Não criar DATABASE_TYPE

Não criar:

```text
DATABASE_TYPE
DATABASE_PROVIDER
DATABASE_ENGINE
PERSISTENCE_TYPE
```

A regra deve continuar sendo:

```text
INTEGRATION_MODE=LOCAL
```

usa MongoDB.

```text
INTEGRATION_MODE=AWS
```

usa DynamoDB.

---

# 6. Persistência habilitada

Substituir completamente:

```text
MONGODB_ENABLED
```

por:

```text
PERSISTENCE_ENABLED
```

Não manter `MONGODB_ENABLED` como configuração ativa, alias, fallback ou compatibilidade temporária.

Adicionar em `Settings`:

```python
persistence_enabled: bool = Field(
    default=True,
    alias="PERSISTENCE_ENABLED",
)
```

Adicionar:

```text
persistence_enabled
```

ao parser booleano já existente.

A habilitação da persistência deve ser independente do backend:

```text
PERSISTENCE_ENABLED=true
```

significa que a aplicação deve persistir apostas.

O backend é escolhido exclusivamente por:

```text
INTEGRATION_MODE
```

Portanto:

```text
PERSISTENCE_ENABLED=true + INTEGRATION_MODE=LOCAL
```

usa:

```text
MongoDB
```

e:

```text
PERSISTENCE_ENABLED=true + INTEGRATION_MODE=AWS
```

usa:

```text
DynamoDB
```

Quando:

```text
PERSISTENCE_ENABLED=false
```

a aplicação não deve persistir apostas em nenhum backend.

---

# 7. Composition root

Alterar:

```text
src/api/dependencies.py
```

Hoje há algo semelhante a:

```python
database = MongoDatabase(
    uri=resolved_settings.mongodb_uri,
    database_name=resolved_settings.mongodb_database,
)

bet_repository = BeanieBetRepository(
    database=database,
)
```

Refatorar para:

```python
if resolved_settings.integration_mode == "AWS":
    bet_repository = DynamoDbBetRepository(
        table_name=resolved_settings.dynamodb_table_name,
    )
else:
    database = MongoDatabase(
        uri=resolved_settings.mongodb_uri,
        database_name=resolved_settings.mongodb_database,
    )

    bet_repository = BeanieBetRepository(
        database=database,
    )
```

A partir deste ponto:

```text
ListPlacedBetsUseCase
GetPlacedBetUseCase
PlacedBetService
```

devem receber apenas:

```text
BetRepositoryPort
```

sem saber qual implementação foi criada.


A criação de `PlacedBetService` deve depender de:

```python
resolved_settings.persistence_enabled
```

e não de qualquer variável específica de MongoDB.

Exemplo conceitual:

```python
bet_persistence = (
    PlacedBetService(
        repository=bet_repository,
        selected_lottery_modality=resolved_settings.selected_lottery_modality,
    )
    if resolved_settings.persistence_enabled
    else None
)
```

---

# 8. Estrutura dos itens DynamoDB

Para minimizar a refatoração inicial, utilizar:

```text
bet_id
```

como Partition Key.

Tipo:

```text
String
```

Um item deve representar uma aposta persistida.

Exemplo:

```json
{
  "bet_id": "ba5148fab16b45648630e90256389264",
  "lottery_modality": "MEGA_SENA",
  "selected_numbers": [
    "01",
    "05",
    "12",
    "30",
    "45",
    "59"
  ],
  "draw_number": "2920",
  "status": "Efetivada",
  "bet_amount": 6.0,
  "purchase_number": "123456",
  "bet_date": "2026-09-24T04:30:00-03:00"
}
```

---

# 9. Geração de bet_id

MongoDB atualmente utiliza:

```text
PydanticObjectId
```

No DynamoDB não depender de ObjectId.

Utilizar UUID.

Exemplo:

```python
from uuid import uuid4

bet_id = uuid4().hex
```

ou:

```python
str(uuid4())
```

O formato escolhido deve ser consistente.

`find_by_id()` não deve tentar converter o ID DynamoDB para:

```text
PydanticObjectId
```

---

# 10. Conversão de Decimal

DynamoDB suporta:

```text
Decimal
```

via boto3.

Nunca utilizar `float` diretamente para valores monetários.

Para:

```text
bet_amount
```

usar:

```python
Decimal
```

Na conversão de retorno:

```python
Decimal(str(item["bet_amount"]))
```

e garantir:

```python
.quantize(Decimal("0.01"))
```

---

# 11. Datas

Persistir:

```text
bet_date
```

como string ISO-8601.

Exemplo:

```text
2026-09-24T04:30:00-03:00
```

Salvar:

```python
purchase.purchase_datetime.isoformat()
```

Ler:

```python
datetime.fromisoformat(...)
```

Manter a normalização de timezone já utilizada no projeto.

Se existir:

```python
with_utc(...)
```

continuar usando-a no retorno do DTO.

---

# 12. save()

Implementar:

```python
save(
    lottery_modality,
    purchase,
)
```

Cada:

```text
BetResult
```

presente em:

```text
PurchaseResult.bets
```

deve gerar um item DynamoDB.

Preferir:

```python
table.batch_writer()
```

Exemplo:

```python
with table.batch_writer() as batch:
    for bet in purchase.bets:
        batch.put_item(Item=item)
```

Se:

```python
bet.amount is None
```

manter comportamento compatível com MongoDB:

```python
raise ValueError(
    "Valor da aposta é obrigatório para persistência."
)
```

Se não houver apostas:

```python
purchase.bets == []
```

não executar escrita.

---

# 13. find_by_id()

Implementar utilizando:

```python
get_item
```

Exemplo:

```python
response = table.get_item(
    Key={
        "bet_id": bet_id,
    }
)
```

Se não houver:

```text
Item
```

retornar:

```python
None
```

Se o identificador for vazio:

```text
""
" "
```

levantar:

```python
ValueError(
    "Identificador da aposta inválido."
)
```

---

# 14. find_all()

O objetivo desta primeira refatoração é:

```text
mínima alteração
```

Portanto não redesenhar agora toda modelagem do DynamoDB.

Inicialmente implementar:

```text
Scan
```

com paginação completa:

```python
while True:
    response = table.scan(...)
```

Verificar:

```text
LastEvaluatedKey
```

e continuar até finalizar.

Depois converter os itens para:

```text
PlacedBetResult
```

e aplicar os filtros existentes:

```text
lottery_modality
draw_number
start_date
end_date
```

em Python.

Ordenar:

```text
bet_date DESC
```

para manter o comportamento atual do MongoDB.

---

# 15. Observação sobre Scan

Não otimizar prematuramente utilizando GSI nesta primeira etapa.

O objetivo inicial é:

```text
migrar com baixo impacto
```

e manter a API atual.

Adicionar comentário/TODO indicando que futuramente podem ser criados GSIs para:

```text
lottery_modality + bet_date
draw_number
purchase_number
```

quando o volume justificar.

---

# 16. Mapper DynamoDB -> DTO

Criar método privado:

```python
_to_result(...)
```

que converta um item DynamoDB para:

```text
PlacedBetResult
```

Exemplo conceitual:

```python
PlacedBetResult(
    bet_id=str(item["bet_id"]),
    lottery_modality=LotteryModality(
        str(item["lottery_modality"])
    ),
    selected_numbers=[
        str(number)
        for number in item["selected_numbers"]
    ],
    draw_number=str(item["draw_number"]),
    status=str(item["status"]),
    bet_amount=Decimal(
        str(item["bet_amount"])
    ).quantize(
        Decimal("0.01")
    ),
    purchase_number=str(
        item["purchase_number"]
    ),
    bet_date=...
)
```

---

# 17. Atualizar exports

Alterar:

```text
src/infrastructure/database/repositories/__init__.py
```

para exportar:

```python
BeanieBetRepository
DynamoDbBetRepository
```

Exemplo:

```python
__all__ = [
    "BeanieBetRepository",
    "DynamoDbBetRepository",
]
```

Atualizar também:

```text
src/infrastructure/database/__init__.py
```

para expor:

```text
MongoDatabase
BetModel
BeanieBetRepository
DynamoDbBetRepository
```

---

# 18. Settings

Em:

```text
src/infrastructure/config/settings.py
```

manter:

```python
integration_mode: Literal["LOCAL", "AWS"]
```

Adicionar:

```python
dynamodb_table_name: str = Field(
    default="loto-bot-bets",
    alias="DYNAMODB_TABLE_NAME",
)
```

Adicionar obrigatoriamente:

```text
PERSISTENCE_ENABLED
```

ao parser booleano existente.

Não criar outra variável para decidir o banco.

---

# 19. .env.example

O ambiente local deve continuar semelhante a:

```text
INTEGRATION_MODE=LOCAL
PERSISTENCE_ENABLED=true

MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=loto_bot

DYNAMODB_TABLE_NAME=loto-bot-bets
```

Embora:

```text
DYNAMODB_TABLE_NAME
```

não seja utilizada em LOCAL, pode permanecer documentada no arquivo.

---

# 20. Ambiente AWS

No:

```text
template.yaml
```

o bootstrap deve criar:

```text
INTEGRATION_MODE=AWS
```

e:

```text
DYNAMODB_TABLE_NAME=<nome-da-tabela>
```

Exemplo:

```bash
echo 'INTEGRATION_MODE=AWS'
echo 'DYNAMODB_TABLE_NAME=${DynamoDbTableName}'
```

Não configurar MongoDB como mecanismo ativo no ambiente AWS.

---

# 21. Criar a tabela DynamoDB antes do SAM deploy

A tabela DynamoDB **não deve ser criada pelo `template.yaml` do SAM**.

Ela deve ser tratada como infraestrutura persistente e criada em uma etapa anterior ao deploy da aplicação.

Criar scripts próprios em:

```text
scripts/create-dynamodb-aws.ps1
scripts/delete-dynamodb-aws.ps1
```

Fluxo esperado:

```text
1. create-dynamodb-aws.ps1
        |
        v
   DynamoDB criado/validado
        |
        v
2. sam deploy
        |
        v
   EC2 / IAM / aplicação
        |
        v
3. DYNAMODB_TABLE_NAME
   informado ao stack
```

Essa separação é obrigatória porque o histórico de apostas deve possuir ciclo de vida independente da EC2 e da stack principal da aplicação.

Uma recriação ou exclusão da stack SAM não deve apagar automaticamente os dados persistidos.

---

# 21.1 Script `create-dynamodb-aws.ps1`

Criar:

```text
scripts/create-dynamodb-aws.ps1
```

O script deve aceitar pelo menos:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$AwsProfile,

    [Parameter(Mandatory = $true)]
    [string]$AwsRegion,

    [string]$DynamoDbTableName = "loto-bot-bets"
)
```

Criar:

```powershell
$AwsCommon = @(
    "--region", $AwsRegion,
    "--profile", $AwsProfile
)
```

---

# 21.2 Validar AWS CLI e identidade

Antes de criar qualquer recurso:

```powershell
Get-Command aws -ErrorAction Stop
```

Validar credenciais:

```powershell
$Identity = aws sts get-caller-identity @AwsCommon
```

Se falhar:

```powershell
throw "Não foi possível validar as credenciais AWS."
```

---

# 21.3 Criação idempotente

O script deve verificar se a tabela já existe antes de tentar criá-la.

Exemplo:

```powershell
$ExistingTable = & aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    --query "Table.TableName" `
    --output text `
    @AwsCommon 2>$null
```

Se a tabela existir:

```text
não recriar
```

Apenas validar seu estado e configuração.

Se não existir:

```text
criar
```

---

# 21.4 Estrutura inicial da tabela

A tabela deve utilizar:

```text
Partition Key: bet_id
Tipo: String
```

Exemplo de criação:

```powershell
& aws dynamodb create-table `
    --table-name $DynamoDbTableName `
    --attribute-definitions `
        AttributeName=bet_id,AttributeType=S `
    --key-schema `
        AttributeName=bet_id,KeyType=HASH `
    --billing-mode PAY_PER_REQUEST `
    --tags `
        Key=Application,Value=loto-bot `
        Key=Environment,Value=aws `
    @AwsCommon
```

Para esta primeira versão utilizar:

```text
PAY_PER_REQUEST
```

O objetivo é manter a infraestrutura simples e adequada ao volume inicialmente baixo e irregular do LotoBot.

Não configurar:

```text
ReadCapacityUnits
WriteCapacityUnits
```

quando:

```text
BillingMode=PAY_PER_REQUEST
```

---

# 21.5 Aguardar a tabela ficar ACTIVE

A criação da tabela DynamoDB é assíncrona.

Após:

```text
create-table
```

executar:

```powershell
& aws dynamodb wait table-exists `
    --table-name $DynamoDbTableName `
    @AwsCommon
```

Depois validar:

```powershell
$TableStatus = & aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    --query "Table.TableStatus" `
    --output text `
    @AwsCommon
```

Esperado:

```text
ACTIVE
```

Caso contrário:

```powershell
throw "Tabela DynamoDB não está ACTIVE: $TableStatus"
```

---

# 21.6 Validar a chave primária existente

Se a tabela já existir, confirmar que:

```text
bet_id
```

é a partition key.

Exemplo conceitual:

```powershell
$HashKey = & aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    --query "Table.KeySchema[?KeyType=='HASH'].AttributeName | [0]" `
    --output text `
    @AwsCommon
```

Validar:

```powershell
if ($HashKey -ne "bet_id") {
    throw "Tabela DynamoDB '$DynamoDbTableName' possui Partition Key incompatível: '$HashKey'."
}
```

Não continuar o deploy utilizando uma tabela incompatível.

---

# 21.7 Tags

Garantir tags:

```text
Application=loto-bot
Environment=aws
ManagedBy=script
```

Opcionalmente:

```text
Purpose=bet-history
```

---

# 21.8 Output do script

Ao concluir, imprimir:

```text
DynamoDB table: loto-bot-bets
Status: ACTIVE
Region: us-east-1
```

Também disponibilizar o nome para o próximo passo.

Exemplo:

```powershell
Write-Output $DynamoDbTableName
```

ou armazenar:

```powershell
$DynamoDbTableName
```

no script orquestrador.

---

# 21.9 Script de exclusão

Criar:

```text
scripts/delete-dynamodb-aws.ps1
```

Esse script deve ser separado do cleanup normal da EC2.

Não apagar a tabela automaticamente ao remover:

```text
EC2
Security Group
Stack SAM
túnel SOCKS5
```

A exclusão da tabela deve ser uma ação explicitamente solicitada.

Exigir confirmação explícita, por exemplo:

```powershell
param(
    [switch]$Force
)
```

Sem:

```text
-Force
```

o script deve abortar ou pedir confirmação interativa.

A intenção é proteger o histórico de apostas.

---

# 21.10 Não criar scripts adicionais de deploy/orquestração

Criar scripts **somente para o DynamoDB**.

Os únicos novos scripts previstos por esta tarefa são:

```text
scripts/create-dynamodb-aws.ps1
scripts/delete-dynamodb-aws.ps1
```

Não criar:

```text
scripts/deploy-loto-bot-aws.ps1
scripts/deploy-aws.ps1
scripts/setup-aws.ps1
scripts/provision-aws.ps1
```

ou qualquer outro script para:

```text
sam build
sam validate
sam deploy
upload de artifact
criação de VPC
criação de EC2
criação de Security Group
criação de túnel SOCKS5
bootstrap da aplicação
```

Essas etapas já estão documentadas em:

```text
docs/AWS_FREE_TIER_MIGRATION_WITH_PROXY_SOCKS5_STEP_BY_STEP.md
```

A tarefa deve apenas atualizar esse guia para inserir a execução do script DynamoDB na posição correta antes do `sam deploy`.

Fluxo desejado no guia:

```text
Etapas já existentes no guia
        |
        v
create-dynamodb-aws.ps1
        |
        v
validar DynamoDB ACTIVE
        |
        v
etapas já existentes de artifact/SAM
        |
        v
sam deploy
```

Não duplicar em scripts aquilo que já está documentado no guia.

---

# 21.11 Alterar o `template.yaml`

O SAM não deve conter:

```yaml
Type: AWS::DynamoDB::Table
```

Remover qualquer recurso `BetTable` previamente planejado.

Adicionar apenas um parâmetro:

```yaml
Parameters:
  DynamoDbTableName:
    Type: String
    Description: Existing DynamoDB table used by LotoBot.
```

Opcionalmente adicionar validação:

```yaml
    MinLength: 3
```

O template deve assumir que a tabela já existe.

---

# 21.12 Injetar o nome no ambiente AWS

No bootstrap da EC2:

```bash
echo 'INTEGRATION_MODE=AWS'
echo 'DYNAMODB_TABLE_NAME=${DynamoDbTableName}'
```

Resultado esperado em:

```text
/etc/loto-bot.env
```

```text
INTEGRATION_MODE=AWS
DYNAMODB_TABLE_NAME=loto-bot-bets
```

---

# 21.13 `samconfig.local.toml`

Adicionar o nome da tabela em:

```text
parameter_overrides
```

Exemplo:

```toml
DynamoDbTableName="loto-bot-bets"
```

O guia passo a passo deve mostrar como reutilizar esse valor no `samconfig.local.toml` ou no comando `sam deploy` já documentado.

---

# 21.14 Independência do ciclo de vida

O comportamento esperado deve ser:

```text
DynamoDB
   |
   | permanece existente
   |
   +---------------------------+
                               |
            +------------------+------------------+
            |                                     |
        Stack v1                              Stack v2
        EC2 antiga                            EC2 nova
```

A tabela deve sobreviver a:

```text
sam delete
recriação da EC2
novo deploy
rollback da aplicação
troca da AMI
```

salvo quando o usuário executar explicitamente:

```text
delete-dynamodb-aws.ps1
```

---

# 22. IAM

A role da EC2 deve receber apenas as permissões DynamoDB necessárias.

Adicionar:

```yaml
- Sid: PersistBetsInDynamoDb
  Effect: Allow
  Action:
    - dynamodb:BatchWriteItem
    - dynamodb:GetItem
    - dynamodb:PutItem
    - dynamodb:Scan
  Resource: !Sub >
    arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${DynamoDbTableName}
```

Não utilizar:

```yaml
Resource: "*"
```

Não conceder:

```text
dynamodb:*
```

Aplicar princípio de least privilege.

---

# 23. IPv6 / dual-stack

A arquitetura atual da branch utiliza:

```text
EC2 sem IPv4 público
IPv6
```

Garantir que o acesso DynamoDB funcione nesse cenário.

Caso necessário configurar boto3:

```python
from botocore.config import Config

Config(
    use_dualstack_endpoint=True,
)
```

Exemplo:

```python
boto3.resource(
    "dynamodb",
    config=Config(
        use_dualstack_endpoint=True,
    ),
)
```

Entretanto, verificar a compatibilidade com a estratégia atual da branch e evitar introduzir VPC Endpoint DynamoDB pago se não for necessário.

---

# 24. Não criar DynamoDB VPC Interface Endpoint

Não criar automaticamente:

```text
AWS::EC2::VPCEndpoint
```

de tipo Interface apenas para DynamoDB.

DynamoDB possui características diferentes de serviços baseados em interface endpoints.

O objetivo deste ajuste é evitar recursos que adicionem custo desnecessário.

---

# 25. Testes unitários obrigatórios

Criar:

```text
tests/unit/test_dynamodb_bet_repository.py
```

Não acessar AWS real.

Criar doubles/fakes para:

```text
DynamoDB resource
Table
batch_writer
scan
get_item
```

---

# 26. Testar save()

Cenário:

```text
PurchaseResult
1 aposta
```

Executar:

```python
repository.save(...)
```

Validar:

```text
1 item escrito
lottery_modality correto
draw_number correto
bet_amount Decimal
purchase_number correto
bet_date ISO-8601
bet_id gerado
```

---

# 27. Testar múltiplas apostas

Criar compra com:

```text
2 ou mais BetResult
```

Confirmar:

```text
um item por aposta
```

---

# 28. Testar compra sem apostas

Quando:

```python
purchase.bets == []
```

não deve haver chamada de escrita.

---

# 29. Testar amount=None

Quando:

```python
bet.amount is None
```

esperar:

```python
ValueError
```

com mensagem equivalente a:

```text
Valor da aposta é obrigatório para persistência.
```

---

# 30. Testar find_by_id()

Testar:

```text
item encontrado
item não encontrado
id vazio
```

---

# 31. Testar find_all()

Testar:

```text
sem filtros
lottery_modality
draw_number
start_date
end_date
combinação de filtros
```

Confirmar ordenação:

```text
bet_date DESC
```

---

# 32. Testar paginação de Scan

O fake DynamoDB deve simular:

```text
LastEvaluatedKey
```

Exemplo:

```text
page 1
page 2
```

Confirmar que:

```text
find_all()
```

retorna itens de todas as páginas.

---

# 33. Testar selection do repository

Criar testes para:

```text
build_container()
```

ou extrair uma pequena factory testável.

Validar:

```text
INTEGRATION_MODE=LOCAL
```

gera:

```text
BeanieBetRepository
```

e:

```text
INTEGRATION_MODE=AWS
```

gera:

```text
DynamoDbBetRepository
```

Evitar conectar MongoDB ou AWS nesses testes.

Usar monkeypatch/mocks.

---

# 34. Compatibilidade do comportamento

Os endpoints atuais de histórico de apostas devem continuar funcionando sem alteração de contrato.

Por exemplo:

```text
GET /api/v1/bets
```

e consultas equivalentes existentes no projeto não devem precisar saber qual banco está sendo utilizado.

Os DTOs retornados devem continuar sendo:

```text
PlacedBetResult
```

---

# 35. Não modificar Playwright

Não modificar a lógica de:

```text
Playwright
Chromium
SOCKS5
proxy
login
seleção da loteria
compra
pagamento
```

Essa refatoração deve ser exclusivamente de persistência e infraestrutura associada ao DynamoDB.

---

# 36. Não modificar clients de integração sem necessidade

Não alterar desnecessariamente:

```text
GmailReaderClient
MailSenderClient
WhatsAppNotifyClient
```

Esses componentes já utilizam:

```text
INTEGRATION_MODE
```

para o comportamento LOCAL/AWS.

A nova seleção de banco deve seguir o mesmo conceito.

---

# 37. Não adicionar dependência desnecessária

`boto3` já está presente no projeto.

Não adicionar ORM para DynamoDB como:

```text
PynamoDB
DynamoDBMapper
```

nesta etapa.

Usar:

```text
boto3
```

diretamente.

---

# 38. Não remover Beanie

O ambiente LOCAL continuará utilizando:

```text
Beanie
MongoDB
```

Portanto não remover do:

```text
pyproject.toml
```

as dependências:

```text
beanie
motor
pymongo
```

---

# 39. Logging

Adicionar logs úteis na seleção do banco, evitando dados sensíveis.

Exemplo:

```python
logger.info(
    "Configurando persistência DynamoDB para ambiente AWS"
)
```

ou:

```python
logger.info(
    "Configurando persistência MongoDB para ambiente LOCAL"
)
```

Nunca registrar:

```text
CPF
senha
CVV
tokens
segredos
```

---

# 40. Fail-fast

No ambiente AWS:

```text
INTEGRATION_MODE=AWS
```

se:

```text
DYNAMODB_TABLE_NAME
```

for vazio ou inválido, falhar de forma clara durante a inicialização ou no primeiro uso.

Não executar fallback silencioso para MongoDB.

Regra obrigatória:

```text
AWS nunca deve cair automaticamente para MongoDB.
```

Da mesma forma:

```text
LOCAL
```

não deve tentar usar DynamoDB automaticamente.

---

# 41. Arquitetura final obrigatória

```text
LOCAL
=====

FastAPI
   |
   v
Application
   |
   v
BetRepositoryPort
   |
   v
BeanieBetRepository
   |
   v
MongoDatabase
   |
   v
MongoDB
```

```text
AWS
===

FastAPI
   |
   v
Application
   |
   v
BetRepositoryPort
   |
   v
DynamoDbBetRepository
   |
   v
boto3
   |
   v
Amazon DynamoDB
```

---

# 42. Configuração final esperada — LOCAL

Arquivo `.env`:

```text
INTEGRATION_MODE=LOCAL
PERSISTENCE_ENABLED=true

MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=loto_bot

DYNAMODB_TABLE_NAME=loto-bot-bets
```

Resultado:

```text
MongoDB
```

deve ser utilizado.

---

# 43. Configuração final esperada — AWS

No `/etc/loto-bot.env`:

```text
INTEGRATION_MODE=AWS
PERSISTENCE_ENABLED=true

DYNAMODB_TABLE_NAME=loto-bot-bets
```

Resultado:

```text
DynamoDB
```

deve ser utilizado.

Mesmo que estejam presentes variáveis:

```text
MONGODB_URI
MONGODB_DATABASE
```

elas não devem ser utilizadas quando:

```text
INTEGRATION_MODE=AWS
```

---

# 44. CloudFormation Output

Como a tabela DynamoDB é criada antes do deploy e não pertence ao stack SAM, o output pode apenas refletir o parâmetro recebido:

```yaml
Outputs:
  DynamoDbBetTableName:
    Description: Existing DynamoDB table used by LotoBot.
    Value: !Ref DynamoDbTableName
```

Esse output é informativo.

A criação, alteração estrutural e exclusão da tabela continuam sob responsabilidade dos scripts próprios de infraestrutura.

---

# 44.1 Atualizar o guia `AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md`

Também é obrigatório atualizar o arquivo:

```text
docs/AWS_FREE_TIER_MIGRATION_WITH_PROXY_SOCKS5_STEP_BY_STEP.md
```

O guia deve refletir a nova ordem real de provisionamento.

A criação/validação do DynamoDB deve ocorrer **antes** do:

```text
sam deploy
```

O guia não pode continuar sugerindo que o SAM cria a tabela.

Preservar as etapas já existentes no guia e inserir apenas o novo passo de DynamoDB antes do `sam deploy`.

A ordem deve ficar conceitualmente:

```text
... etapas já existentes ...
        |
        v
Criar/validar DynamoDB
        |
        v
... etapas já existentes de preparação do deploy ...
        |
        v
sam deploy
        |
        v
... etapas posteriores já existentes ...
```

Não reescrever o processo existente desnecessariamente e não transformar as demais etapas em novos scripts.

---

## 44.1.1 Adicionar seção de criação do DynamoDB

Inserir uma seção antes do `sam deploy`, por exemplo:

```markdown
## Criar/validar a tabela DynamoDB

Antes de executar o `sam deploy`, crie ou valide a tabela de apostas:

```powershell
.\scripts\create-dynamodb-aws.ps1 `
    -AwsProfile $AwsProfile `
    -AwsRegion $AwsRegion `
    -DynamoDbTableName $DynamoDbTableName
```

A tabela deve terminar no estado:

```text
ACTIVE
```
```

O guia deve explicar que esse passo é obrigatório no ambiente AWS.

---

## 44.1.2 Declarar a variável `DynamoDbTableName`

No início do fluxo PowerShell documentado, adicionar:

```powershell
$DynamoDbTableName = "loto-bot-bets"
```

junto das demais variáveis, por exemplo:

```powershell
$AwsProfile = "AWSCLI260909"
$AwsRegion = "us-east-1"
$InstanceType = "t3.micro"
$DynamoDbTableName = "loto-bot-bets"
```

---

## 44.1.3 Passar a tabela para o SAM

O guia deve mostrar explicitamente que o nome da tabela é fornecido ao stack.

Se utilizar `samconfig.local.toml`, documentar:

```toml
DynamoDbTableName="loto-bot-bets"
```

dentro de:

```text
parameter_overrides
```

Se utilizar linha de comando, mostrar equivalente:

```powershell
sam deploy `
    --parameter-overrides `
        DynamoDbTableName=$DynamoDbTableName `
        ...
```

Não usar:

```text
BetTable
```

como recurso criado pelo template.

---

## 44.1.4 Validar a tabela antes do deploy

O guia deve incluir uma validação explícita:

```powershell
$TableStatus = aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    --query "Table.TableStatus" `
    --output text `
    @AwsCommon

if ($TableStatus -ne "ACTIVE") {
    throw "Tabela DynamoDB não está ACTIVE: $TableStatus"
}
```

Também validar a partition key:

```powershell
$HashKey = aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    --query "Table.KeySchema[?KeyType=='HASH'].AttributeName | [0]" `
    --output text `
    @AwsCommon

if ($HashKey -ne "bet_id") {
    throw "Partition Key incompatível: $HashKey"
}
```

---

## 44.1.5 Atualizar diagrama do fluxo de deploy

O guia deve incluir um diagrama semelhante a:

```text
PowerShell local
      |
      +--> create-dynamodb-aws.ps1
      |          |
      |          v
      |      DynamoDB ACTIVE
      |
      +--> build/package artifact
      |
      +--> upload S3
      |
      +--> sam validate --lint
      |
      +--> sam deploy
                 |
                 v
                EC2
                 |
                 +--> INTEGRATION_MODE=AWS
                 +--> DYNAMODB_TABLE_NAME=loto-bot-bets
                 |
                 v
              LotoBot
```

---

## 44.1.6 Atualizar seção de variáveis de ambiente

O guia deve documentar claramente:

### LOCAL

```text
INTEGRATION_MODE=LOCAL
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=loto_bot
```

Persistência:

```text
MongoDB + Beanie
```

### AWS

```text
INTEGRATION_MODE=AWS
DYNAMODB_TABLE_NAME=loto-bot-bets
```

Persistência:

```text
DynamoDB + boto3
```

Não documentar MongoDB como banco ativo no ambiente AWS.

---

## 44.1.7 Atualizar seção de cleanup

O guia deve deixar explícito:

```text
sam delete
```

ou scripts de cleanup da EC2 **não devem excluir a tabela DynamoDB**.

Adicionar observação semelhante a:

```markdown
> A tabela `loto-bot-bets` possui ciclo de vida independente da stack SAM.
> Remover a stack da aplicação não remove o histórico de apostas.
```

A exclusão deve ser feita somente de forma explícita:

```powershell
.\scripts\delete-dynamodb-aws.ps1 `
    -AwsProfile $AwsProfile `
    -AwsRegion $AwsRegion `
    -DynamoDbTableName $DynamoDbTableName `
    -Force
```

---

## 44.1.8 Atualizar seção de troubleshooting

Adicionar comandos para diagnóstico:

```powershell
aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    @AwsCommon
```

Listar quantidade aproximada de itens:

```powershell
aws dynamodb describe-table `
    --table-name $DynamoDbTableName `
    --query "Table.ItemCount" `
    --output text `
    @AwsCommon
```

Listar itens de teste:

```powershell
aws dynamodb scan `
    --table-name $DynamoDbTableName `
    --max-items 10 `
    @AwsCommon
```

---

## 44.1.9 Atualizar seção de pré-requisitos

Adicionar:

```text
Permissão para:
- dynamodb:CreateTable
- dynamodb:DescribeTable
- dynamodb:TagResource
- dynamodb:DeleteTable
```

para os scripts administrativos locais.

Isso é diferente das permissões da EC2, que devem continuar limitadas às operações de runtime:

```text
dynamodb:GetItem
dynamodb:PutItem
dynamodb:BatchWriteItem
dynamodb:Scan
```

---

## 44.1.10 Critério de aceite da documentação

A tarefa só estará concluída se o arquivo:

```text
docs/AWS_FREE_TIER_MIGRATION_WITH_PROXY_SOCKS5_STEP_BY_STEP.md
```

for atualizado e contiver:

- [ ] criação do DynamoDB antes do SAM;
- [ ] execução de `create-dynamodb-aws.ps1`;
- [ ] variável `$DynamoDbTableName`;
- [ ] validação `ACTIVE`;
- [ ] validação da partition key `bet_id`;
- [ ] passagem de `DynamoDbTableName` para o SAM;
- [ ] arquitetura LOCAL=MongoDB;
- [ ] arquitetura AWS=DynamoDB;
- [ ] cleanup sem exclusão automática da tabela;
- [ ] comando explícito de exclusão;
- [ ] troubleshooting DynamoDB;
- [ ] ordem completa e atualizada do deploy.

---

# 44.2 Ajustar obrigatoriamente `template.yaml`

O arquivo:

```text
template.yaml
```

deve ser atualizado como parte obrigatória da tarefa.

A tabela DynamoDB será criada previamente por script próprio, portanto o SAM **não deve criar nem destruir a tabela**.

---

## 44.2.1 Adicionar parâmetro `DynamoDbTableName`

Adicionar em:

```yaml
Parameters:
```

um parâmetro semelhante a:

```yaml
DynamoDbTableName:
  Type: String
  Description: Existing DynamoDB table used by LotoBot.
  MinLength: 3
```

Esse parâmetro representa uma tabela já existente, criada anteriormente por:

```text
scripts/create-dynamodb-aws.ps1
```

---

## 44.2.2 Não criar `AWS::DynamoDB::Table`

O arquivo:

```text
template.yaml
```

não deve conter:

```yaml
Type: AWS::DynamoDB::Table
```

para a tabela de apostas.

Não criar recursos como:

```text
BetTable
LotoBotBetTable
DynamoDbBetTable
```

dentro da stack principal.

O ciclo de vida da tabela deve permanecer independente do ciclo de vida da aplicação.

---

## 44.2.3 Atualizar IAM da EC2

Na role utilizada pela instância EC2, adicionar apenas as permissões necessárias para runtime:

```yaml
- Sid: PersistBetsInDynamoDb
  Effect: Allow
  Action:
    - dynamodb:BatchWriteItem
    - dynamodb:GetItem
    - dynamodb:PutItem
    - dynamodb:Scan
  Resource: !Sub >
    arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${DynamoDbTableName}
```

Se o código utilizar outras operações comprovadamente necessárias, adicioná-las de forma explícita.

Não usar:

```yaml
Action: dynamodb:*
```

Não usar:

```yaml
Resource: "*"
```

---

## 44.2.4 Atualizar bootstrap `/etc/loto-bot.env`

Na geração do arquivo:

```text
/etc/loto-bot.env
```

garantir:

```bash
echo 'INTEGRATION_MODE=AWS'
echo 'DYNAMODB_TABLE_NAME=${DynamoDbTableName}'
```

Incluir obrigatoriamente:

```bash
echo 'PERSISTENCE_ENABLED=true'
```

No ambiente AWS não deve existir:

```text
MONGODB_ENABLED
```

A configuração ativa deve representar:

```text
AWS -> DynamoDB
```

---

## 44.2.5 MongoDB no template

Variáveis como:

```text
MONGODB_URI
MONGODB_DATABASE
```

não são necessárias para a persistência AWS.

Preferencialmente removê-las do bootstrap AWS se não forem utilizadas por nenhum outro componente.

Caso sejam mantidas temporariamente por compatibilidade, documentar que:

```text
INTEGRATION_MODE=AWS
```

faz com que sejam ignoradas.

Remover qualquer referência a:

```text
MONGODB_ENABLED
```

do bootstrap da EC2 AWS.

---

## 44.2.6 Output da tabela

Adicionar output informativo:

```yaml
Outputs:
  DynamoDbBetTableName:
    Description: Existing DynamoDB table used by LotoBot.
    Value: !Ref DynamoDbTableName
```

Esse output não representa ownership da tabela pela stack.

---

## 44.2.7 Metadata do template

Atualizar comentários e metadata que descrevem a arquitetura.

Onde houver referência exclusiva a persistência MongoDB, atualizar para refletir:

```text
LOCAL -> MongoDB
AWS -> DynamoDB
```

Documentar também que:

```text
DynamoDB é infraestrutura persistente externa à stack SAM.
```

---

## 44.2.8 Validação do template

Após o ajuste executar:

```powershell
sam validate --lint
```

e garantir sucesso.

Também verificar:

```powershell
sam validate
```

caso já faça parte do fluxo atual.

---

# 44.3 Ajustar obrigatoriamente `samconfig.local.toml`

O arquivo:

```text
samconfig.local.toml
```

também deve ser atualizado obrigatoriamente.

Ele deve fornecer ao SAM o nome da tabela criada previamente.

---

## 44.3.1 Adicionar `DynamoDbTableName`

Adicionar aos:

```text
parameter_overrides
```

o parâmetro:

```text
DynamoDbTableName="<dynamodb-table-name>"
```

Exemplo:

```toml
parameter_overrides = "VpcId=\"<loto-bot-vpc-id>\" SubnetId=\"<loto-bot-subnet-id>\" AmiId=\"<ami-id>\" InstanceType=\"t3.micro\" KeyName=\"loto-bot\" AllowedSshIpv6Cidr=\"<ipv6-publico-local>/128\" ArtifactBucket=\"<artifact-bucket>\" ArtifactKey=\"<artifact-key>\" ArtifactSha256=\"<artifact-sha256>\" ApplicationSecretArn=\"<application-secret-arn>\" GmailReaderFunctionArn=\"<gmail-reader-function-arn>\" MailSenderFunctionArn=\"<mail-sender-function-arn>\" WhatsAppNotifyUrl=\"<whatsapp-notify-private-url>\" IntegrationSecurityGroupId=\"<loto-bot-integration-security-group-id>\" DynamoDbTableName=\"<dynamodb-table-name>\" ConfirmPayment=\"false\" RootVolumeSize=20"
```

Preservar os demais parâmetros atualmente necessários.

---

## 44.3.2 Remover parâmetros obsoletos relacionados ao MongoDB

Remover completamente qualquer parâmetro:

```text
MongoDbEnabled
MONGODB_ENABLED
```

de:

```text
template.yaml
samconfig.local.toml
.env.example
Settings
scripts
documentação
testes
```

Não manter compatibilidade temporária.

A habilitação da persistência deve ser controlada somente por:

```text
PERSISTENCE_ENABLED
```

A escolha do backend deve ser controlada somente por:

```text
INTEGRATION_MODE
```

Regra final:

```text
PERSISTENCE_ENABLED=true
INTEGRATION_MODE=LOCAL
```

usa MongoDB.

```text
PERSISTENCE_ENABLED=true
INTEGRATION_MODE=AWS
```

usa DynamoDB.

```text
PERSISTENCE_ENABLED=false
```

não persiste apostas.

---

## 44.3.3 Não colocar dados sensíveis no samconfig

Não adicionar ao:

```text
samconfig.local.toml
```

dados como:

```text
CPF
senha
CVV
e-mail sensível
tokens
segredos
```

Esses dados devem continuar vindo de:

```text
AWS Secrets Manager
```

---

## 44.3.4 Consistência entre script e samconfig

O valor criado/validado pelo script:

```powershell
$DynamoDbTableName
```

deve ser exatamente o mesmo utilizado pelo:

```text
samconfig.local.toml
```

ou passado dinamicamente pelo script de deploy.

Evitar duplicação inconsistente.

Não criar script de deploy para propagar esse valor.

A consistência deve ser garantida por:

```text
scripts/create-dynamodb-aws.ps1
samconfig.local.toml
template.yaml
docs/AWS_FREE_TIER_MIGRATION_WITH_PROXY_SOCKS5_STEP_BY_STEP.md
```

O guia deve orientar o usuário a utilizar o mesmo valor de:

```powershell
$DynamoDbTableName
```

na criação/validação da tabela e no parâmetro passado ao SAM.

---

## 44.3.5 Exemplo de fluxo integrado

O documento deve orientar algo equivalente a:

```powershell
$AwsProfile = "AWSCLI260909"
$AwsRegion = "us-east-1"
$InstanceType = "t3.micro"
$DynamoDbTableName = "loto-bot-bets"

.\scripts\create-dynamodb-aws.ps1 `
    -AwsProfile $AwsProfile `
    -AwsRegion $AwsRegion `
    -DynamoDbTableName $DynamoDbTableName

sam validate --lint

sam deploy `
    --config-file samconfig.local.toml `
    --parameter-overrides `
        DynamoDbTableName=$DynamoDbTableName
```

Se o projeto já utilizar `parameter_overrides` integralmente no `samconfig.local.toml`, preservar esse padrão e apenas garantir que `DynamoDbTableName` esteja presente.

---

# 44.4 Consistência entre os quatro componentes

A implementação deve manter consistentes:

```text
scripts/create-dynamodb-aws.ps1
template.yaml
samconfig.local.toml
docs/AWS_FREE_TIER_MIGRATION_WITH_PROXY_SOCKS5_STEP_BY_STEP.md
```

A relação deve ser:

```text
create-dynamodb-aws.ps1
        |
        | cria/valida
        v
loto-bot-bets
        |
        | nome da tabela
        v
samconfig.local.toml
        |
        | parameter override
        v
template.yaml
        |
        | DYNAMODB_TABLE_NAME
        v
/etc/loto-bot.env
        |
        v
DynamoDbBetRepository
```

Nenhum desses componentes deve utilizar um nome de tabela diferente.

---

# 44.5 Critérios de aceite específicos de `template.yaml` e `samconfig.local.toml`

Adicionar aos critérios de aceite:

- [ ] `template.yaml` recebe `DynamoDbTableName`.
- [ ] `template.yaml` não cria `AWS::DynamoDB::Table`.
- [ ] IAM da EC2 referencia somente a tabela informada.
- [ ] `/etc/loto-bot.env` recebe `DYNAMODB_TABLE_NAME`.
- [ ] `/etc/loto-bot.env` recebe `INTEGRATION_MODE=AWS`.
- [ ] `samconfig.local.toml` contém `DynamoDbTableName`.
- [ ] `samconfig.local.toml` não contém segredos.
- [ ] `MongoDbEnabled` foi removido de `template.yaml`.
- [ ] `MONGODB_ENABLED` foi removido de `samconfig.local.toml`, `.env.example`, código, scripts e documentação.
- [ ] `PERSISTENCE_ENABLED` está presente nos ambientes LOCAL e AWS.
- [ ] `sam validate --lint` passa após as alterações.
- [ ] guia passo a passo contém a mesma ordem e os mesmos nomes de parâmetros.

---

# 45. README / documentação

Atualizar a documentação para deixar explícito:

```text
LOCAL = MongoDB
AWS   = DynamoDB
```

Adicionar uma seção semelhante a:

```markdown
## Persistência

O backend utilizado depende de `INTEGRATION_MODE`.

| INTEGRATION_MODE | Database |
|---|---|
| LOCAL | MongoDB |
| AWS | DynamoDB |
```

---

# 46. Compatibilidade com testes atuais

Todos os testes existentes devem continuar passando.

Executar:

```bash
pytest
```

Se a cobertura estiver configurada para:

```text
100%
```

os novos arquivos também devem ser cobertos conforme as regras atuais do projeto.

---

# 47. Ruff

Executar:

```bash
ruff check .
```

e:

```bash
ruff format --check .
```

Corrigir todos os problemas introduzidos pela refatoração.

---

# 48. SAM

Executar:

```bash
sam validate --lint
```

O:

```text
template.yaml
```

deve permanecer válido.

---

# 48.1 Escopo obrigatório dos scripts

Esta tarefa deve criar ou alterar scripts apenas relacionados ao DynamoDB.

Permitido:

```text
scripts/create-dynamodb-aws.ps1
scripts/delete-dynamodb-aws.ps1
```

Não permitido criar novos scripts para outras etapas de infraestrutura ou deploy.

Não criar scripts para:

```text
SAM deploy
SAM build
artifact S3
EC2
VPC
Subnet
Security Group
SSH
SOCKS5
Secrets Manager
Lambda
Nginx
bootstrap
```

Se alguma dessas etapas precisar ser ajustada, modificar somente:

```text
template.yaml
samconfig.local.toml
docs/AWS_FREE_TIER_MIGRATION_WITH_PROXY_SOCKS5_STEP_BY_STEP.md
```

conforme necessário.

A documentação existente continua sendo a fonte do passo a passo completo de deploy.

---

# 49. Critérios de aceite

A tarefa só estará concluída se todos estes requisitos forem atendidos:

- [ ] `INTEGRATION_MODE=LOCAL` utiliza MongoDB.
- [ ] `MONGODB_ENABLED` foi removido completamente.
- [ ] `PERSISTENCE_ENABLED` controla apenas se haverá persistência.
- [ ] `INTEGRATION_MODE=AWS` utiliza DynamoDB.
- [ ] Não existe `DATABASE_TYPE`.
- [ ] Não existe fallback automático AWS -> MongoDB.
- [ ] `BeanieBetRepository` continua funcional.
- [ ] Existe `DynamoDbBetRepository`.
- [ ] Ambos implementam `BetRepositoryPort`.
- [ ] `save()` funciona em DynamoDB.
- [ ] `find_all()` funciona em DynamoDB.
- [ ] `find_by_id()` funciona em DynamoDB.
- [ ] DynamoDB utiliza `bet_id` como partition key.
- [ ] Valores monetários usam `Decimal`.
- [ ] Datas são persistidas em ISO-8601.
- [ ] Paginação de `Scan` foi implementada.
- [ ] Tabela DynamoDB é criada por script próprio antes do `sam deploy`.
- [ ] `template.yaml` não cria `AWS::DynamoDB::Table`.
- [ ] `template.yaml` recebe `DynamoDbTableName` como parâmetro.
- [ ] `samconfig.local.toml` foi atualizado com `DynamoDbTableName`.
- [ ] `template.yaml` e `samconfig.local.toml` estão consistentes com os scripts pré-deploy.
- [ ] Apenas scripts relacionados ao DynamoDB foram criados.
- [ ] Nenhum novo script de `sam deploy` ou orquestração AWS foi criado.
- [ ] `create-dynamodb-aws.ps1` é idempotente.
- [ ] `create-dynamodb-aws.ps1` aguarda a tabela ficar `ACTIVE`.
- [ ] `delete-dynamodb-aws.ps1` não é chamado automaticamente pelo cleanup da aplicação.
- [ ] IAM possui apenas permissões necessárias.
- [ ] `DYNAMODB_TABLE_NAME` é injetado no ambiente AWS.
- [ ] LOCAL continua utilizando `MONGODB_URI`.
- [ ] AWS não depende de MongoDB.
- [ ] Testes unitários DynamoDB não acessam AWS real.
- [ ] Testes existentes continuam passando.
- [ ] `pytest` passa.
- [ ] `ruff check .` passa.
- [ ] `ruff format --check .` passa.
- [ ] `sam validate --lint` passa.
- [ ] `../docs/AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md` foi atualizado com os scripts executados antes do `sam deploy`.

---

# 50. Resultado esperado

Após a implementação:

```text
                 INTEGRATION_MODE
                       |
           +-----------+-----------+
           |                       |
        LOCAL                     AWS
           |                       |
           v                       v
       MongoDB                  DynamoDB
           |                       |
           v                       v
BeanieBetRepository      DynamoDbBetRepository
           \                       /
            \                     /
             +----BetRepositoryPort
                       |
                       v
                Application
```

A aplicação deve continuar funcionando com o mesmo contrato de API e de casos de uso, alterando apenas o adapter de persistência conforme o ambiente.

---

# 51. Entrega esperada do agente

Ao concluir, apresentar:

1. lista dos arquivos alterados;
2. lista dos arquivos criados;
3. resumo da decisão arquitetural;
4. comportamento em `LOCAL`;
5. comportamento em `AWS`;
6. modelagem da tabela DynamoDB;
7. scripts exclusivamente relacionados ao DynamoDB (`create-dynamodb-aws.ps1` e `delete-dynamodb-aws.ps1`);
8. permissões IAM adicionadas;
9. testes criados;
10. resultado de:

```text
pytest
ruff check .
ruff format --check .
sam validate --lint
```

11. resumo das alterações realizadas em `template.yaml`;
12. resumo das alterações realizadas em `samconfig.local.toml`;
13. resumo das alterações realizadas em `../docs/AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md`;
14. qualquer limitação ou melhoria futura identificada.

Não encerrar a tarefa apenas descrevendo o que deve ser feito.

Implementar efetivamente todas as alterações necessárias.
