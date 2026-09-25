# Sugestões de melhorias — `mail-sender-aws`

> **Estado após os ajustes:** a Lambda foi retirada da VPC do cliente, os parâmetros de rede e a policy de ENI foram removidos, o IAM do SES restringe `ses:FromAddress` ao remetente configurado, e os logs de erro foram sanitizados. README e guia SAM descrevem a invocação direta. As seções abaixo registram as sugestões originais e podem descrever o estado anterior.

## 1. Contexto

Repositório:

```text
https://github.com/cams7-ai/mail-sender-aws.git
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

A proposta atual substitui o antigo fluxo HTTP/API Gateway por invocação direta da Lambda pelo LotoBot usando IAM.

---

# 2. Arquitetura atual

O fluxo implementado atualmente é conceitualmente:

```text
LotoBot EC2
    |
    | lambda:InvokeFunction
    | via Lambda Interface VPC Endpoint
    v
AWS Lambda service
    |
    v
MailSenderFunction
    |
    | Lambda ENI dentro da VPC
    v
Subnet compartilhada do LotoBot
    |
    | IPv6
    v
Amazon SES
```

No `template.yaml`, a Lambda está vinculada à VPC por:

```yaml
VpcConfig:
  SecurityGroupIds:
    - !Ref MailSenderSecurityGroup
  SubnetIds:
    - !Ref SubnetId
  Ipv6AllowedForDualStack: true
```

Também existem:

```text
VpcId
SubnetId
MailSenderSecurityGroup
AWSLambdaVPCAccessExecutionRole
AWS_USE_DUALSTACK_ENDPOINT=true
```

---

# 3. Principal melhoria recomendada

## Remover a `MailSenderFunction` da VPC

A invocação privada da Lambda pelo LotoBot ocorre contra a API do serviço Lambda.

O:

```text
Lambda Interface VPC Endpoint
```

é necessário no lado do consumidor, ou seja:

```text
LotoBot EC2
```

Ele não exige que a função Lambda invocada esteja anexada à mesma VPC.

Arquitetura simplificada:

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
MailSenderFunction
    |
    v
Amazon SES
```

A Lambda pode permanecer fora da VPC e utilizar a conectividade gerenciada do serviço Lambda para acessar o SES.

---

# 4. Benefícios de remover a Lambda da VPC

Remover:

```text
VpcConfig
VpcId
SubnetId
MailSenderSecurityGroup
AWSLambdaVPCAccessExecutionRole
Ipv6AllowedForDualStack
```

reduz:

```text
acoplamento com o LotoBot
dependência da subnet
dependência de rota IPv6
dependência de Security Group
criação de ENIs
complexidade operacional
pontos de falha
```

A responsabilidade fica melhor separada:

```text
mail-sender-aws
    |
    +--> valida payload
    +--> envia SES

loto-bot
    |
    +--> possui conectividade privada ao Lambda API
    +--> possui lambda:InvokeFunction
    +--> conhece FunctionArn
```

---

# 5. Arquitetura recomendada

```text
VPC LotoBot
=================================================

LotoBot EC2
     |
     | private Lambda Invoke
     v
Lambda Interface VPC Endpoint

================ AWS managed boundary ============

AWS Lambda Service
     |
     v
MailSenderFunction
     |
     v
Amazon SES
```

O `mail-sender-aws` deixa de depender diretamente de:

```text
VPC do LotoBot
Subnet do LotoBot
Security Group do LotoBot
rota ::/0
```

---

# 6. Simplificar `template.yaml`

## Situação atual

O template recebe:

```text
VpcId
SubnetId
SesFrom
```

e cria:

```text
MailSenderSecurityGroup
VpcConfig
```

## Sugestão

Manter apenas o que a função realmente necessita.

Estrutura conceitual:

```yaml
Parameters:
  SesFrom:
    Type: String
    NoEcho: true

Globals:
  Function:
    Runtime: python3.12
    Timeout: 10
    MemorySize: 128
    Architectures:
      - x86_64

Resources:

  MailSenderFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: lambda_handler.handler

      Environment:
        Variables:
          SES_FROM: !Ref SesFrom

      Policies:
        - Statement:
            - Effect: Allow
              Action:
                - ses:SendEmail
              Resource: ...

  MailSenderFunctionLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${MailSenderFunction}"
      RetentionInDays: 7

Outputs:

  FunctionArn:
    Value: !GetAtt MailSenderFunction.Arn

  FunctionName:
    Value: !Ref MailSenderFunction
```

---

# 7. Remover parâmetros de rede do SAM

Remover:

```text
VpcId
SubnetId
```

do:

```text
template.yaml
samconfig.local.toml
docs/AWS_SAM_MIGRATION_STEP_BY_STEP.md
```

se nenhuma outra funcionalidade depender deles.

Isso deixa o `mail-sender-aws` independente da infraestrutura física do LotoBot.

---

# 8. Simplificar `samconfig.local.toml`

## Atual

```toml
parameter_overrides = "VpcId="<loto-bot-vpc-id>" SubnetId="<loto-bot-subnet-id>" SesFrom="<remetente-verificado@example.com>""
```

## Sugerido

```toml
parameter_overrides = "SesFrom="<remetente-verificado@example.com>""
```

Isso reduz muito o acoplamento entre os dois projetos.

---

# 9. Remover `MailSenderSecurityGroup`

Se a Lambda não estiver na VPC, remover:

```yaml
MailSenderSecurityGroup:
  Type: AWS::EC2::SecurityGroup
```

e toda configuração associada a:

```text
DNS egress
HTTPS IPv6
VpcId
```

A Lambda passa a utilizar a rede gerenciada do serviço AWS.

---

# 10. Remover `AWSLambdaVPCAccessExecutionRole`

Atualmente a função possui:

```yaml
AWSLambdaVPCAccessExecutionRole
```

Essa policy existe para permitir criação e gerenciamento das interfaces de rede necessárias à Lambda conectada à VPC.

Sem `VpcConfig`, ela deixa de ser necessária.

Remover reduz permissões e melhora least privilege.

---

# 11. Reavaliar `AWS_USE_DUALSTACK_ENDPOINT`

Atualmente:

```yaml
AWS_USE_DUALSTACK_ENDPOINT: "true"
```

foi adicionada para preservar acesso IPv6 ao SES a partir da subnet.

Se a Lambda sair da VPC, essa configuração deixa de ser necessária para resolver conectividade.

Sugestão:

```text
remover
```

a menos que exista outro requisito explícito para forçar endpoints dual-stack.

---

# 12. Manter Lambda Interface Endpoint no lado do LotoBot

A simplificação da função **não significa remover necessariamente**:

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

sem exigir:

```text
NAT
IPv4 público
Internet Gateway para IPv4
```

A responsabilidade pelo endpoint deve ficar no projeto/infraestrutura do LotoBot.

---

# 13. Invocação direta da Lambda

A mudança feita em:

```text
src/lambda_handler.py
```

é boa.

A lógica:

```python
direct_invocation = "requestContext" not in event
```

permite aceitar diretamente:

```json
{
  "to": "destino@example.com",
  "subject": "Assunto",
  "body": "Mensagem",
  "message_type": "HTML"
}
```

Isso combina bem com:

```python
lambda.invoke(...)
```

do LotoBot.

---

# 14. Preservar `Bet...`? Não aplicável

Este projeto não deve receber lógica de infraestrutura pertencente a:

```text
LotoBot
WhatsApp Notify
MongoDB
DynamoDB
```

Manter o escopo estrito:

```text
envio de e-mail
SES
Lambda
```

Isso ajuda a manter o serviço pequeno e desacoplado.

---

# 15. Compatibilidade HTTP antiga

O handler ainda mantém suporte a:

```text
requestContext
routeKey
rawPath
body
isBase64Encoded
```

Mesmo que o deploy AWS atual não utilize API Gateway.

## Sugestão

Na primeira fase:

```text
manter compatibilidade
```

para reduzir risco.

Em uma etapa futura, caso API Gateway seja definitivamente removido, considerar simplificar o handler para direct invocation apenas.

---

# 16. Possível simplificação futura do handler

Hoje a resposta mantém formato:

```json
{
  "statusCode": 200,
  "body": "{"message":"E-mail enviado com sucesso."}"
}
```

Isso é útil para compatibilidade HTTP.

Se o contrato futuro for somente Lambda Invoke, poderia retornar:

```json
{
  "message": "E-mail enviado com sucesso."
}
```

Mas essa mudança afetaria o cliente do LotoBot.

Portanto não é recomendada durante esta migração inicial.

---

# 17. IAM do SES

Atualmente:

```yaml
Action:
  - ses:SendEmail
Resource: "*"
```

Funciona, mas pode ser restringido.

## Sugestão

Avaliar policy limitada à identidade SES autorizada.

Objetivo:

```text
MailSenderFunction
      |
      +--> pode enviar apenas usando identidade autorizada
```

Evitar, quando tecnicamente possível:

```text
Resource: "*"
```

---

# 18. `SesFrom`

Atualmente:

```yaml
SesFrom:
  Type: String
  NoEcho: true
```

Essa configuração é adequada.

Embora o remetente não seja necessariamente um segredo forte, manter `NoEcho` é conservador e simples.

Pode-se adicionar validação de formato, se desejado.

---

# 19. Amazon SES Sandbox

A documentação já alerta corretamente que, no sandbox:

```text
remetente e destinatário
```

precisam estar verificados.

Manter esse aviso em destaque.

Adicionar checklist explícito:

```text
[ ] remetente verificado
[ ] região correta
[ ] status do sandbox conhecido
[ ] acesso de produção solicitado quando necessário
```

---

# 20. Região do SES

Garantir que:

```text
SES_FROM
```

esteja verificado na mesma região utilizada pela Lambda.

Documentar que identidades SES são regionais.

Evitar confusão quando:

```text
identidade existe em us-east-1
Lambda está em outra região
```

---

# 21. CloudWatch Logs

A retenção atual:

```yaml
RetentionInDays: 7
```

é adequada para custo baixo.

Manter.

Evitar retenção indefinida sem necessidade.

---

# 22. Logs sensíveis

Não registrar:

```text
body do e-mail
destinatários desnecessariamente
dados pessoais
tokens
segredos
```

Especialmente no tratamento:

```python
except Exception:
```

Caso logging de erro seja adicionado, registrar:

```text
tipo da exceção
request id
código AWS
```

sem conteúdo do e-mail.

---

# 23. Melhorar observabilidade de erros SES

Hoje:

```python
except Exception:
    return _error_response(
        500,
        "email_send_error",
        "Falha ao enviar e-mail.",
    )
```

Isso protege detalhes internos do cliente, o que é bom.

Porém dificulta troubleshooting.

## Sugestão

Adicionar log interno sanitizado.

Exemplo conceitual:

```python
logger.exception(
    "Falha ao enviar e-mail via SES"
)
```

desde que nenhum conteúdo sensível do payload seja incluído.

---

# 24. Diferenciar erros SES

Em uma evolução futura, tratar especificamente:

```text
MessageRejected
MailFromDomainNotVerified
TooManyRequests
Throttling
AccessDenied
```

e mapear para respostas coerentes.

Exemplo:

```text
configuration_error
email_rejected
throttled
email_send_error
```

Sem expor detalhes sensíveis.

---

# 25. Testes

A branch já adicionou:

```text
test_handle_event_accepts_direct_lambda_invocation
```

Isso é importante.

Adicionar também testes para:

```text
direct invocation inválida
direct invocation com HTML
body Base64 HTTP
body HTTP que não é objeto JSON
SES_FROM ausente
erro inesperado de SES
```

---

# 26. Testar `message_type`

Garantir cobertura explícita para:

```text
HTML
TEXT
valor ausente
case insensitive
```

Como:

```python
(message.message_type or "").upper() == "HTML"
```

define o formato.

---

# 27. Testar `SesEmailSender`

Criar ou manter testes isolados validando que:

```text
HTML -> Content.Simple.Body.Html
TEXT -> Content.Simple.Body.Text
```

e que:

```text
Destination.ToAddresses
FromEmailAddress
Subject
```

sejam enviados corretamente.

---

# 28. CI

A branch atualmente não apresenta workflow/status checks associados ao HEAD.

Criar:

```text
.github/workflows/ci.yml
```

com pelo menos:

```text
pytest
sam validate --lint
sam build
```

Se Ruff for introduzido:

```text
ruff check .
ruff format --check .
```

---

# 29. Proteção da branch

A branch:

```text
AWS_FREE_TIER_MIGRATION
```

não está protegida e não possui required status checks.

Após criar CI, considerar exigir:

```text
pytest
SAM validate
SAM build
```

antes do merge para:

```text
main
```

---

# 30. README está desatualizado

Esse é um dos principais problemas atuais.

O README ainda descreve:

```text
API Gateway
cliente HTTP
ApiUrl
rota sem autenticação
```

Mas a branch implementa:

```text
direct Lambda invocation
IAM
FunctionArn
```

Atualizar completamente a seção de arquitetura.

---

# 31. Arquitetura correta no README

Substituir:

```text
Cliente HTTP
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
   | IAM lambda:InvokeFunction
   v
AWS Lambda
   |
   v
MailSenderFunction
   |
   v
Amazon SES
```

---

# 32. Remover aviso de rota HTTP pública

O README contém aviso semelhante a:

```text
A rota ainda não possui autenticação.
```

Isso não corresponde mais ao deploy AWS atual.

Substituir por:

```text
A integração AWS não expõe API Gateway ou Function URL.
O acesso é autorizado por IAM através de lambda:InvokeFunction.
```

---

# 33. Atualizar seção de deploy do README

Remover instruções relacionadas a:

```text
ApiUrl
execute-api
API Gateway endpoint
```

Adicionar:

```text
FunctionArn
FunctionName
aws lambda invoke
```

---

# 34. Atualizar `docs/AWS_SAM_MIGRATION_STEP_BY_STEP.md`

O guia já está mais alinhado com a nova arquitetura.

A principal correção é remover a afirmação:

```text
MailSenderFunction na mesma VPC/subnet dual-stack
```

e substituir por:

```text
LotoBot usa endpoint privado do serviço Lambda
MailSenderFunction não precisa estar anexada à VPC
```

---

# 35. Simplificar pré-requisitos do guia

Se a Lambda sair da VPC, remover como pré-requisitos do mail-sender:

```text
VpcId
SubnetId
subnet dual-stack
rota ::/0
DNS da VPC
```

Esses passam a ser requisitos do LotoBot, não do `mail-sender-aws`.

---

# 36. Atualizar fluxo do guia

Fluxo recomendado:

```text
1. validar credenciais AWS
2. validar identidade SES
3. executar testes
4. sam validate
5. sam build
6. sam deploy
7. obter FunctionArn
8. configurar FunctionArn no LotoBot
9. executar smoke test via aws lambda invoke
```

---

# 37. Smoke test

Manter o teste direto:

```powershell
aws lambda invoke
```

porque ele testa exatamente o contrato de produção.

Exemplo:

```powershell
$Payload = '{"to":"destino@example.com","subject":"Teste","body":"Mensagem","message_type":"TEXT"}'

aws lambda invoke `
  --function-name $MailSenderFunctionArn `
  --cli-binary-format raw-in-base64-out `
  --payload $Payload `
  response.json
```

---

# 38. Integração com o LotoBot

No LotoBot:

```text
MAIL_SENDER_FUNCTION_NAME=<FunctionArn>
```

é adequado.

A role da EC2 deve possuir:

```text
lambda:InvokeFunction
```

apenas sobre:

```text
MailSenderFunctionArn
```

Evitar:

```text
Resource: "*"
```

---

# 39. Naming

Embora a variável atual seja:

```text
MAIL_SENDER_FUNCTION_NAME
```

o valor pode ser um ARN.

Isso funciona tecnicamente com boto3.

Em uma futura limpeza de naming, considerar:

```text
MAIL_SENDER_FUNCTION_ARN
```

Mas isso não é prioridade se gerar impacto no LotoBot.

---

# 40. Timeout

Atualmente:

```yaml
Timeout: 10
```

é razoável para uma chamada SES simples.

Monitorar latência real.

Se não houver timeout observado, manter 10 segundos ajuda a limitar custo e travamentos.

---

# 41. Memória

Atualmente:

```yaml
MemorySize: 128
```

é suficiente para:

```text
Pydantic
boto3
SES
```

em princípio.

Não aumentar sem evidência de necessidade.

---

# 42. Arquitetura x86_64

Atualmente:

```yaml
Architectures:
  - x86_64
```

É simples e compatível.

Como o projeto depende apenas de Python/boto3/Pydantic, futuramente pode-se avaliar:

```text
arm64
```

mas isso não é prioridade.

---

# 43. Cold start

Remover a Lambda da VPC também reduz complexidade associada ao attach de rede.

Além disso, o pacote é pequeno:

```text
boto3
pydantic
código próprio
```

Isso favorece cold starts baixos.

---

# 44. Dependência `boto3`

O runtime Lambda já inclui boto3, mas versionar explicitamente:

```text
boto3>=1.35
```

no pacote garante controle de versão.

Isso é aceitável.

Monitorar apenas aumento do tamanho do bundle.

---

# 45. `src/requirements.txt`

Manter simples:

```text
boto3
pydantic[email]
```

Evitar adicionar frameworks HTTP como:

```text
FastAPI
Uvicorn
Mangum
```

se a função continuar sendo direct invocation.

---

# 46. Clean Architecture

A separação atual é boa:

```text
lambda_handler
     |
     v
SendEmailUseCase
     |
     v
EmailSender
     |
     v
SesEmailSender
```

Preservar.

Evitar colocar lógica SES diretamente no handler.

---

# 47. Tratamento de configuração

`SesEmailSender` carrega:

```text
SES_FROM
```

e levanta:

```text
ConfigurationError
```

Isso é adequado.

Manter configuração fora do domínio.

---

# 48. Não criar API Gateway novamente sem necessidade

A integração atual é interna à AWS.

Não reintroduzir:

```text
API Gateway
Function URL
token compartilhado
API key
```

a menos que apareça um consumidor externo real.

IAM + direct invocation é mais adequado para o LotoBot.

---

# 49. Custos

A arquitetura simplificada elimina componentes desnecessários do próprio `mail-sender-aws`.

Custos principais tendem a ser:

```text
Lambda invocations
Lambda duration
CloudWatch Logs
Amazon SES
S3/SAM artifacts
```

O Lambda Interface Endpoint, se mantido, pertence à infraestrutura do LotoBot e deve ser contabilizado separadamente.

---

# 50. Ordem recomendada das melhorias

## Fase 1 — Arquitetura

1. remover `VpcConfig`;
2. remover `VpcId` e `SubnetId`;
3. remover `MailSenderSecurityGroup`;
4. remover `AWSLambdaVPCAccessExecutionRole`;
5. remover `AWS_USE_DUALSTACK_ENDPOINT` se desnecessário.

## Fase 2 — Configuração

6. simplificar `samconfig.local.toml`;
7. atualizar IAM SES;
8. manter `SesFrom`.

## Fase 3 — Documentação

9. atualizar `README.md`;
10. atualizar `AWS_SAM_MIGRATION_STEP_BY_STEP.md`;
11. documentar claramente direct Lambda invocation.

## Fase 4 — Qualidade

12. ampliar testes;
13. adicionar CI;
14. proteger merge com required checks.

## Fase 5 — Observabilidade

15. adicionar logging interno sanitizado;
16. tratar erros SES relevantes;
17. revisar alarmes se o volume crescer.

---

# 51. Checklist antes do merge

- [ ] `MailSenderFunction` não depende desnecessariamente da VPC.
- [ ] `VpcId` removido se não for necessário.
- [ ] `SubnetId` removido se não for necessário.
- [ ] `MailSenderSecurityGroup` removido.
- [ ] `AWSLambdaVPCAccessExecutionRole` removido.
- [ ] `AWS_USE_DUALSTACK_ENDPOINT` revisado.
- [ ] `samconfig.local.toml` simplificado.
- [ ] README atualizado para direct invocation.
- [ ] Guia SAM atualizado.
- [ ] IAM SES revisado.
- [ ] `pytest` passa.
- [ ] `sam validate --lint` passa.
- [ ] `sam build` passa.
- [ ] smoke test com `aws lambda invoke` funciona.
- [ ] LotoBot consegue invocar a função usando o ARN.
- [ ] logs não expõem corpo ou dados sensíveis de e-mail.

---

# 52. Conclusão

A branch `AWS_FREE_TIER_MIGRATION` está indo na direção correta ao substituir:

```text
API Gateway público
```

por:

```text
IAM + lambda:InvokeFunction
```

A principal melhoria arquitetural é remover a própria função Lambda da VPC.

O resultado recomendado é:

```text
LotoBot EC2
     |
     | private Lambda Invoke
     v
Lambda Interface Endpoint
     |
     v
AWS Lambda Service
     |
     v
MailSenderFunction
     |
     v
Amazon SES
```

Com isso, o `mail-sender-aws` fica:

```text
mais simples
mais desacoplado
com menos IAM
com menos recursos de rede
mais fácil de testar
mais fácil de operar
```
