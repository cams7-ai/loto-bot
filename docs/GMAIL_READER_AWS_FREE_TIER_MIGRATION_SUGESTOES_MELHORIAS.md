# Sugestões de melhorias — `gmail-reader-aws`

> **Estado após os ajustes:** a Lambda foi retirada da VPC do cliente, sem parâmetros de rede ou policy de ENI; o cache do cliente é renovado uma vez após falha de refresh OAuth. README e guia SAM descrevem a invocação direta e a rotação do segredo. As seções abaixo registram as sugestões originais e podem descrever o estado anterior. O LotoBot usa o endpoint Lambda dual stack; o endpoint privado antigo pode ser removido somente após validação na EC2.

## 1. Contexto

Repositório:

```text
https://github.com/cams7-ai/gmail-reader-aws.git
```

Branch analisada:

```text
AWS_FREE_TIER_MIGRATION
```

A branch está atualmente:

```text
2 commits à frente da main
0 commits atrás
```

As alterações estão concentradas em:

```text
docs/AWS_SAM_MIGRATION_STEP_BY_STEP.md
samconfig.local.toml
src/lambda_handler.py
template.yaml
tests/test_lambda_handler.py
```

A proposta atual substitui o fluxo HTTP/API Gateway pela invocação direta da Lambda pelo LotoBot usando IAM.

---

# 2. Arquitetura atual

O fluxo implementado atualmente é:

```text
LotoBot EC2
    |
    | lambda:InvokeFunction
    v
Lambda Interface VPC Endpoint
    |
    v
AWS Lambda Service
    |
    v
GmailReaderFunction
    |
    | ENI da Lambda
    v
VPC/Subnet do LotoBot
    |
    | IPv6
    +--> AWS Secrets Manager
    |
    +--> Gmail API
```

No `template.yaml`, isso aparece por meio de:

```yaml
VpcConfig:
  SecurityGroupIds:
    - !Ref GmailReaderSecurityGroup
  SubnetIds:
    - !Ref SubnetId
  Ipv6AllowedForDualStack: true
```

Além de:

```text
VpcId
SubnetId
GmailReaderSecurityGroup
AWSLambdaVPCAccessExecutionRole
AWS_USE_DUALSTACK_ENDPOINT=true
```

---

# 3. Principal melhoria recomendada

## Remover a `GmailReaderFunction` da VPC

A invocação privada feita pelo LotoBot ocorre contra a API do serviço Lambda.

O:

```text
Lambda Interface VPC Endpoint
```

é necessário no lado do consumidor:

```text
LotoBot EC2
```

para executar:

```text
lambda:InvokeFunction
```

privadamente.

A função Lambda de destino não precisa estar anexada à mesma VPC para ser invocada por esse endpoint.

Arquitetura recomendada:

```text
LotoBot EC2
    |
    | private lambda:InvokeFunction
    v
Lambda Interface VPC Endpoint
    |
    v
AWS Lambda Service
    |
    v
GmailReaderFunction
    |
    +--> Secrets Manager
    |
    v
Gmail API
```

---

# 4. Benefícios de remover a Lambda da VPC

Remover:

```text
VpcConfig
VpcId
SubnetId
GmailReaderSecurityGroup
AWSLambdaVPCAccessExecutionRole
Ipv6AllowedForDualStack
```

reduz:

```text
acoplamento com o LotoBot
dependência de subnet
dependência de rota IPv6
dependência de Security Group
criação de ENIs
complexidade de deploy
pontos de falha
```

O serviço passa a depender apenas de:

```text
Secrets Manager
Gmail API
```

---

# 5. Separação de responsabilidades

## `gmail-reader-aws`

Responsável por:

```text
ler segredo OAuth
autenticar no Gmail
consultar mensagens
extrair código
retornar resultado
```

## `loto-bot`

Responsável por:

```text
possuir Lambda Interface VPC Endpoint
possuir lambda:InvokeFunction
conhecer FunctionArn
```

Essa separação deixa os dois projetos mais independentes.

---

# 6. Simplificar `template.yaml`

## Situação atual

O template recebe:

```text
VpcId
SubnetId
GmailOAuthSecretArn
SenderEmail
SubjectFilter
ActivationCodeRegex
WaitTimeoutSeconds
```

## Sugestão

Remover:

```text
VpcId
SubnetId
```

e manter apenas parâmetros funcionais.

Estrutura conceitual:

```yaml
Parameters:

  GmailOAuthSecretArn:
    Type: String

  SenderEmail:
    Type: String

  SubjectFilter:
    Type: String

  ActivationCodeRegex:
    Type: String

  WaitTimeoutSeconds:
    Type: Number

Resources:

  GmailReaderFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: lambda_handler.handler

      Policies:
        - Version: "2012-10-17"
          Statement:
            - Sid: ReadGoogleOAuthSecret
              Effect: Allow
              Action:
                - secretsmanager:GetSecretValue
              Resource: !Ref GmailOAuthSecretArn
```

Sem:

```text
VpcConfig
Security Group
AWSLambdaVPCAccessExecutionRole
```

---

# 7. Remover `GmailReaderSecurityGroup`

Se a Lambda não estiver na VPC, remover:

```yaml
GmailReaderSecurityGroup:
  Type: AWS::EC2::SecurityGroup
```

e regras relacionadas a:

```text
HTTPS IPv6
DNS IPv4
VpcId
```

A função utilizará a rede gerenciada do serviço Lambda.

---

# 8. Remover `AWSLambdaVPCAccessExecutionRole`

Essa policy é necessária para as interfaces de rede associadas a uma Lambda conectada à VPC.

Sem:

```text
VpcConfig
```

ela deixa de ser necessária.

Isso reduz permissões e melhora least privilege.

---

# 9. Reavaliar `AWS_USE_DUALSTACK_ENDPOINT`

Atualmente:

```yaml
AWS_USE_DUALSTACK_ENDPOINT: "true"
```

foi incluído para facilitar acesso IPv6 aos endpoints AWS a partir da subnet.

Se a função sair da VPC, essa configuração deixa de ser necessária para resolver conectividade.

Sugestão:

```text
remover
```

salvo se existir requisito explícito para forçar endpoints dual-stack.

---

# 10. Manter o Lambda Interface Endpoint no LotoBot

A remoção da Lambda da VPC não significa remover:

```text
com.amazonaws.<region>.lambda
```

da infraestrutura do LotoBot.

Esse endpoint continua sendo útil para:

```text
LotoBot EC2
     |
     v
Lambda API
```

sem depender de:

```text
IPv4 público
NAT Gateway
```

O endpoint deve permanecer responsabilidade do LotoBot.

---

# 11. Simplificar `samconfig.local.toml`

## Atual

```toml
parameter_overrides = "VpcId="<loto-bot-vpc-id>" SubnetId="<loto-bot-subnet-id>" GmailOAuthSecretArn="<arn-do-segredo>" WaitTimeoutSeconds=15"
```

## Sugerido

```toml
parameter_overrides = "GmailOAuthSecretArn="<arn-do-segredo>" WaitTimeoutSeconds=15"
```

Isso reduz acoplamento entre projetos.

---

# 12. Secrets Manager

A implementação atual está bem estruturada.

O código:

```python
_get_secrets_client().get_secret_value(
    SecretId=self._settings.gmail_oauth_secret_arn
)
```

usa o ARN configurado.

O IAM está corretamente limitado a:

```text
secretsmanager:GetSecretValue
```

somente sobre:

```text
GmailOAuthSecretArn
```

Essa prática deve ser mantida.

---

# 13. Segredo OAuth fora da stack

A documentação trata o segredo como recurso criado separadamente.

Isso é bom porque:

```text
sam delete
```

não deve apagar automaticamente:

```text
refresh_token
client_id
client_secret
```

Manter esse ciclo de vida independente.

---

# 14. OAuth em AWS

O comportamento atual está correto.

Quando:

```text
GMAIL_OAUTH_SECRET_ARN
```

está definido, o código não executa:

```python
InstalledAppFlow.run_local_server(...)
```

Isso evita login interativo dentro da Lambda.

Manter essa regra.

---

# 15. Refresh token

O segredo deve conter:

```text
refresh_token
client_id
client_secret
token_uri
scopes
```

Nunca armazenar esses dados em:

```text
template.yaml
samconfig.toml
.env versionado
logs
```

---

# 16. Cache do cliente Gmail

O uso de:

```python
@lru_cache(maxsize=1)
def _create_repository()
```

é uma boa otimização.

Em invocações quentes:

```text
repository
Gmail service
credentials
```

podem ser reutilizados.

Isso reduz:

```text
latência
chamadas ao Secrets Manager
cold-path repetido
```

---

# 17. Validar refresh em ambiente warm

Adicionar teste ou smoke test cobrindo:

```text
Lambda permanece warm
access token expira
nova chamada é feita
refresh_token renova access token
consulta Gmail continua funcionando
```

Não é um bug confirmado, mas é um cenário operacional importante.

---

# 18. `lambda_handler.py`

A mudança:

```python
direct_invocation = "requestContext" not in event
```

é adequada.

Com chamada direta:

```python
query = event
```

O LotoBot pode enviar:

```json
{
  "waitTimeoutSeconds": "15"
}
```

Isso combina bem com:

```text
lambda:InvokeFunction
```

---

# 19. Compatibilidade HTTP antiga

O handler ainda suporta:

```text
requestContext
http.method
http.path
queryStringParameters
```

Isso preserva compatibilidade.

Na primeira fase da migração, manter é razoável.

Em etapa futura, caso API Gateway seja definitivamente abandonado, avaliar remoção desse código.

---

# 20. README está desatualizado

O README ainda descreve:

```text
API Gateway HTTP API
cliente HTTP
API REST serverless
endpoint HTTP
```

Mas a branch atual utiliza:

```text
LotoBot
  |
  | IAM
  v
Lambda Invoke
```

Isso deve ser tratado como P0.

---

# 21. Atualizar arquitetura no README

Substituir:

```text
Client
  |
  v
API Gateway
  |
  v
Lambda
```

por:

```text
LotoBot
  |
  | lambda:InvokeFunction
  v
AWS Lambda
  |
  v
GmailReaderFunction
  |
  +--> Secrets Manager
  |
  v
Gmail API
```

---

# 22. Atualizar tipo do projeto no README

Hoje aparece algo equivalente a:

```text
API REST serverless
```

Uma descrição mais adequada seria:

```text
Lambda serverless para leitura de códigos de validação do Gmail
```

ou:

```text
serviço serverless invocado diretamente via AWS Lambda
```

---

# 23. Atualizar seção de deploy do README

Remover referências a:

```text
API Gateway
ApiUrl
HTTP endpoint
```

e adicionar:

```text
FunctionArn
FunctionName
aws lambda invoke
```

---

# 24. Atualizar `docs/AWS_SAM_MIGRATION_STEP_BY_STEP.md`

O guia já está mais alinhado com a arquitetura nova.

A principal correção é remover:

```text
GmailReaderFunction na mesma VPC/subnet dual-stack
```

e substituir por:

```text
LotoBot usa Lambda Interface Endpoint
GmailReaderFunction é executada fora da VPC do cliente
```

---

# 25. Simplificar pré-requisitos do guia

Se a Lambda sair da VPC, remover do projeto `gmail-reader-aws`:

```text
VpcId
SubnetId
rota ::/0
DNS da VPC
subnet dual-stack
```

Esses passam a ser requisitos apenas do LotoBot.

---

# 26. Fluxo recomendado no guia

```text
1. validar AWS CLI/SAM CLI
2. validar configuração Google OAuth
3. criar ou validar segredo no Secrets Manager
4. executar pytest
5. sam validate
6. sam build
7. sam deploy
8. obter FunctionArn
9. configurar FunctionArn no LotoBot
10. smoke test com aws lambda invoke
```

---

# 27. Timeout

Atualmente:

```text
WaitTimeoutSeconds <= 15
Lambda Timeout = 25
```

Essa relação é coerente.

Há margem para:

```text
cold start
Secrets Manager
refresh OAuth
Gmail API
serialização
```

Manter por enquanto.

---

# 28. Semântica do timeout

Hoje:

```text
ValidationCodeTimeoutError
```

retorna:

```text
statusCode = 500
```

Funciona, mas:

```text
nenhum código chegou no prazo
```

não é necessariamente erro interno.

Em uma futura evolução do contrato, avaliar:

```text
408
404
204
```

ou um estado funcional explícito.

Não alterar agora sem revisar o cliente LotoBot.

---

# 29. Filtros do Gmail

Os defaults:

```text
SENDER_EMAIL=logincaixa@caixa.gov.br
SUBJECT_FILTER=Código de Validação
```

são coerentes com o caso de uso.

O serviço ainda valida novamente:

```python
_matches_configured_filters(...)
```

depois da busca na Gmail API.

Isso é uma boa proteção contra resultados inesperados do query parser.

---

# 30. Extração do código

A lógica atual:

```python
match = re.search(regex, body)
digits = re.search(r"\d+", match.group())
```

retorna somente os dígitos.

Manter esse comportamento.

Adicionar testes para variações de HTML/texto e conteúdo inválido.

---

# 31. Logs sensíveis

Manter fora dos logs:

```text
validation code
refresh_token
access_token
client_secret
body do e-mail
conteúdo bruto do segredo
```

O teste:

```text
test_handler_does_not_log_validation_code
```

é muito importante e deve ser mantido.

---

# 32. Melhorar observabilidade

Hoje os erros conhecidos são mapeados.

Pode-se adicionar logging interno sanitizado para:

```text
RefreshError
ConnectionError
TimeoutError
ssl.SSLError
```

sem registrar dados do e-mail ou tokens.

Exemplo conceitual:

```python
logger.exception("Falha ao consultar Gmail API")
```

desde que o contexto seja sanitizado.

---

# 33. X-Ray

O template possui:

```yaml
Tracing: Active
```

Para um serviço pequeno e focado em baixo custo, avaliar se X-Ray permanente é realmente necessário.

Possibilidades:

```text
manter Active em homologação
usar PassThrough em produção
desabilitar até surgir necessidade de tracing
```

Classificação sugerida:

```text
P2
```

---

# 34. CloudWatch Logs

Atualmente:

```yaml
RetentionInDays: 14
```

é uma janela razoável.

Para foco máximo em custo, 7 dias pode ser considerado.

Não há necessidade urgente de mudança.

---

# 35. `DeletionPolicy: Delete`

O Log Group utiliza:

```yaml
DeletionPolicy: Delete
UpdateReplacePolicy: Delete
```

Portanto:

```text
sam delete
```

remove o histórico de logs.

Isso deve ser documentado claramente.

---

# 36. Testes

A branch já possui teste para direct invocation:

```text
test_handler_accepts_direct_lambda_invocation
```

Adicionar também:

```text
direct invocation inválida
timeout ausente
timeout inválido
refresh token revogado
segredo inválido
Gmail API timeout
erro TLS
mensagem sem código
mensagem HTML
```

---

# 37. Testes de `GmailAuthenticator`

Os testes atuais são bons e cobrem:

```text
Secrets Manager
refresh token
login local
não iniciar login interativo na AWS
não gravar token local na AWS
cache do Secrets Manager
```

Manter.

---

# 38. Testes de `GmailRepository`

Reforçar cobertura de:

```text
metadata only
raw message
multipart text/plain
multipart text/html
attachment ignored
internalDate inválido
lista vazia
```

---

# 39. CI

A branch atualmente não possui workflow/status checks associados ao HEAD.

Criar:

```text
.github/workflows/ci.yml
```

com:

```text
pytest
coverage
sam validate --lint
sam build
```

Se Ruff for adotado:

```text
ruff check .
ruff format --check .
```

---

# 40. Cobertura

O projeto possui:

```text
fail_under = 100
```

O CI deve executar a cobertura de forma explícita.

Exemplo:

```powershell
python -m pytest --cov=src --cov-report=term-missing
```

---

# 41. Proteção da branch

A branch:

```text
AWS_FREE_TIER_MIGRATION
```

não está protegida.

Após criar CI, considerar required checks antes do merge para `main`.

---

# 42. Memória da Lambda

Atualmente:

```yaml
MemorySize: 256
```

É razoável porque o projeto utiliza:

```text
google-api-python-client
google-auth
Pydantic/config
```

Não reduzir sem medir duração e cold start.

---

# 43. Arquitetura `x86_64`

Manter:

```yaml
Architectures:
  - x86_64
```

é simples e compatível.

Pode-se avaliar `arm64` futuramente, mas não é prioridade.

---

# 44. Dependências

O pacote inclui:

```text
boto3
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
google-auth
python-dotenv
```

Avaliar futuramente se:

```text
google-auth-oauthlib
```

precisa estar no pacote de produção AWS, já que o login interativo não ocorre na Lambda.

Caso seja necessário apenas para modo local, considerar separar dependências runtime AWS e desenvolvimento/local.

---

# 45. Reduzir tamanho do pacote

O Google API client e bibliotecas OAuth podem aumentar o tamanho da Lambda.

Avaliar:

```text
dependências usadas somente localmente
layers
remoção de bibliotecas desnecessárias em runtime
```

somente se tamanho/cold start se tornar problema.

Não otimizar prematuramente.

---

# 46. Escopo Gmail

Manter:

```text
https://www.googleapis.com/auth/gmail.readonly
```

É apropriado para least privilege.

Não ampliar para:

```text
gmail.modify
gmail.send
mail.google.com
```

sem necessidade.

---

# 47. Rotação do refresh token

Documentar procedimento:

```text
gerar novo token local
validar
atualizar Secrets Manager
não alterar ARN
testar Lambda
revogar token antigo quando aplicável
```

Isso evita necessidade de redeploy para simples rotação.

---

# 48. Integração com o LotoBot

O output:

```text
FunctionArn
```

deve continuar sendo passado ao LotoBot.

No ambiente:

```text
GMAIL_READER_FUNCTION_NAME=<FunctionArn>
```

funciona tecnicamente.

Em futura limpeza de naming, considerar:

```text
GMAIL_READER_FUNCTION_ARN
```

mas não é prioridade.

---

# 49. IAM no LotoBot

A role do consumidor deve possuir:

```text
lambda:InvokeFunction
```

somente sobre:

```text
GmailReaderFunctionArn
```

Evitar:

```text
Resource: "*"
```

---

# 50. Não reintroduzir API Gateway sem necessidade

A integração atual é interna à AWS.

Não reintroduzir:

```text
API Gateway
Function URL
API key
token compartilhado
```

sem consumidor externo real.

IAM + direct Lambda invocation é mais adequado ao cenário.

---

# 51. Ordem recomendada das melhorias

## Fase 1 — Arquitetura

1. remover `VpcConfig`;
2. remover `VpcId`;
3. remover `SubnetId`;
4. remover `GmailReaderSecurityGroup`;
5. remover `AWSLambdaVPCAccessExecutionRole`.

## Fase 2 — Configuração

6. revisar `AWS_USE_DUALSTACK_ENDPOINT`;
7. simplificar `samconfig.local.toml`;
8. manter `GmailOAuthSecretArn`.

## Fase 3 — Documentação

9. atualizar `README.md`;
10. atualizar `AWS_SAM_MIGRATION_STEP_BY_STEP.md`;
11. corrigir arquitetura de direct invocation.

## Fase 4 — Resiliência

12. validar refresh OAuth em Lambda warm;
13. reforçar testes Gmail;
14. documentar rotação do segredo.

## Fase 5 — Qualidade

15. adicionar CI;
16. manter 100% de cobertura;
17. proteger merge com required checks.

## Fase 6 — Custos/observabilidade

18. reavaliar X-Ray;
19. revisar retenção dos logs;
20. monitorar duration/cold starts.

---

# 52. Prioridades

| Prioridade | Ajuste |
|---|---|
| P0 | Remover `VpcConfig` se não houver recurso privado necessário |
| P0 | Atualizar `README.md` para direct Lambda invocation |
| P1 | Remover `VpcId`, `SubnetId` e `GmailReaderSecurityGroup` |
| P1 | Remover `AWSLambdaVPCAccessExecutionRole` |
| P1 | Simplificar `samconfig.local.toml` |
| P1 | Atualizar guia SAM |
| P1 | Validar refresh OAuth em ambiente warm |
| P2 | Reavaliar `AWS_USE_DUALSTACK_ENDPOINT` |
| P2 | Reavaliar `Tracing: Active` |
| P2 | Adicionar CI |
| P3 | Revisar semântica do timeout |

---

# 53. Checklist antes do merge

- [ ] `GmailReaderFunction` não depende desnecessariamente da VPC.
- [ ] `VpcId` removido se não for necessário.
- [ ] `SubnetId` removido se não for necessário.
- [ ] `GmailReaderSecurityGroup` removido.
- [ ] `AWSLambdaVPCAccessExecutionRole` removido.
- [ ] `AWS_USE_DUALSTACK_ENDPOINT` revisado.
- [ ] `samconfig.local.toml` simplificado.
- [ ] README atualizado.
- [ ] Guia SAM atualizado.
- [ ] OAuth secret permanece fora da stack.
- [ ] IAM do segredo é least privilege.
- [ ] LotoBot possui apenas `lambda:InvokeFunction` no ARN necessário.
- [ ] `pytest` passa.
- [ ] cobertura 100% passa.
- [ ] `sam validate --lint` passa.
- [ ] `sam build` passa.
- [ ] smoke test com `aws lambda invoke` funciona.
- [ ] código de validação não aparece em logs.
- [ ] refresh token não aparece em logs.
- [ ] cenário de Lambda warm com token renovado foi validado.

---

# 54. Arquitetura final recomendada

```text
LotoBot EC2
     |
     | private Lambda Invoke
     v
Lambda Interface VPC Endpoint
     |
     v
AWS Lambda Service
     |
     v
GmailReaderFunction
     |
     +--> AWS Secrets Manager
     |
     v
Gmail API
```

Esse desenho mantém:

```text
invocação privada
IAM least privilege
segredo protegido
Gmail readonly
```

e remove dependências de rede desnecessárias do `gmail-reader-aws`.

---

# 55. Conclusão

A branch `AWS_FREE_TIER_MIGRATION` está indo na direção correta ao substituir:

```text
API Gateway
```

por:

```text
IAM + lambda:InvokeFunction
```

e ao manter o OAuth do Gmail no Secrets Manager.

A principal melhoria arquitetural é remover a própria Lambda da VPC do LotoBot.

O resultado tende a ser:

```text
mais simples
mais desacoplado
com menos IAM
com menos recursos de rede
mais fácil de operar
mais fácil de testar
```
