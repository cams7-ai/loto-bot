# Sugestões de melhorias — `AWS_FREE_TIER_MIGRATION`

> **Estado após os ajustes:** o `template.yaml` não abre mais a porta 443 e permite remover o endpoint Lambda por `UseLambdaVpcEndpoint=false` após a versão com cliente dual stack ter sido validada na EC2. O endpoint CloudFormation continua necessário para `cfn-signal` e ganhou checagem prévia. O teste de navegador passou a permitir confirmar a falha sem túnel. As seções abaixo registram as sugestões originais e podem descrever o estado anterior. Não foram executadas as mudanças de descrição da persistência, medição prévia de DynamoDB nem alterações no Chromium ou no tamanho da EC2, conforme solicitado.

## 1. Objetivo

Este documento reúne sugestões de melhoria para a branch `AWS_FREE_TIER_MIGRATION` do projeto **LotoBot**.

Repositório:

```text
https://github.com/cams7-ai/loto-bot.git
```

Branch analisada:

```text
AWS_FREE_TIER_MIGRATION
```

A branch introduz uma arquitetura baseada em:

```text
PC local
   |
   | SSH via IPv6
   v
EC2
   |
   | SOCKS5 reverso em 127.0.0.1:1080
   v
Chromium / Playwright
   |
   v
Loterias Online CAIXA
```

Além disso, integrações internas como Gmail Reader e Mail Sender passam a ser invocadas via AWS Lambda quando:

```text
INTEGRATION_MODE=AWS
```

---

# 2. Resumo das prioridades

| Prioridade | Melhoria | Impacto |
|---|---|---|
| P0 | Revisar a necessidade do `LambdaVpcEndpoint` | Redução de custo AWS |
| P0 | Corrigir inconsistência entre Security Group 443 e Nginx 80 | Evita configuração sem efeito |
| P1 | Validar dependência do endpoint privado do CloudFormation | Evita rollback no deploy |
| P1 | Criar validação automatizada do túnel SOCKS5 | Maior confiabilidade operacional |
| P1 | Adicionar CI para testes, Ruff e SAM Validate | Evita regressões |
| P1 | Melhorar observabilidade do bootstrap da EC2 | Facilita diagnóstico |
| P2 | Separar infraestrutura compartilhada da aplicação | Simplifica manutenção |
| P2 | Tornar scripts PowerShell mais reutilizáveis | Reduz duplicação |
| P2 | Adicionar validações de pré-requisitos antes do deploy | Fail-fast |
| P2 | Documentar estratégia de recuperação do túnel | Melhor operação |
| P3 | Melhorar hardening do systemd | Segurança |
| P3 | Adicionar métricas e health checks específicos | Operação |
| P3 | Revisar atualização do User-Agent fixo | Compatibilidade futura |

---

# 3. Remover ou reavaliar o `LambdaVpcEndpoint`

## Problema

O `template.yaml` cria um endpoint privado de interface:

```yaml
LambdaVpcEndpoint:
  Type: AWS::EC2::VPCEndpoint
  Properties:
    VpcEndpointType: Interface
    ServiceName: !Sub com.amazonaws.${AWS::Region}.lambda
    PrivateDnsEnabled: true
```

Interface VPC Endpoints utilizam AWS PrivateLink e geram custo enquanto permanecem provisionados.

Isso entra em conflito com o objetivo de uma arquitetura orientada ao menor custo possível.

## Sugestão

Verificar se a EC2 pode invocar o endpoint público regional do Lambda utilizando IPv6/dual-stack.

Caso funcione adequadamente, remover:

```yaml
LambdaEndpointSecurityGroup
LambdaVpcEndpoint
```

A chamada Python continuaria simples:

```python
boto3.client("lambda").invoke(...)
```

## Arquitetura simplificada

```text
LotoBot EC2
    |
    | HTTPS IPv6
    v
AWS Lambda public regional endpoint
    |
    +--> gmail-reader
    |
    +--> mail-sender
```

## Benefícios

- menor custo;
- menos recursos CloudFormation;
- menos Security Groups;
- menos dependências de Private DNS;
- deploy mais simples;
- troubleshooting mais simples.

---

# 4. Corrigir `Security Group 443` x `Nginx 80`

## Problema

O Security Group libera:

```yaml
FromPort: 443
ToPort: 443
```

Porém o Nginx é configurado com:

```nginx
server {
    listen 80 default_server;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Portanto:

```text
Security Group
TCP 443
   |
   v
EC2

Nginx escutando apenas TCP 80
```

Não existe processo atendendo a porta 443.

## Sugestão preferencial

Como a aplicação já pode ser acessada através de SSH ou AWS SSM, não expor a API diretamente para a Internet.

Remover:

```yaml
AllowedCidr
```

e:

```yaml
- Description: HTTPS from the authorized client
  IpProtocol: tcp
  FromPort: 443
  ToPort: 443
  CidrIp: !Ref AllowedCidr
```

Manter o Nginx apenas internamente.

## Acesso recomendado

Por SSM Port Forwarding:

```powershell
aws ssm start-session `
    --target <INSTANCE_ID> `
    --document-name AWS-StartPortForwardingSession `
    --parameters portNumber=80,localPortNumber=8080
```

Depois:

```text
http://127.0.0.1:8080
```

Alternativamente, pode-se usar SSH port forwarding.

## Benefícios

- menor superfície de ataque;
- não exige TLS público;
- elimina configuração de porta 443 sem serviço correspondente;
- reduz regras de firewall.

---

# 5. Validar previamente o endpoint privado do CloudFormation

## Problema

O bootstrap da EC2 executa:

```bash
cfn-signal
```

para informar ao CloudFormation que o bootstrap terminou.

A arquitetura atual assume que existe previamente um endpoint privado do CloudFormation com Private DNS habilitado.

Essa dependência está documentada, mas não é criada pelo próprio stack da aplicação.

Caso o endpoint não exista:

```text
EC2 bootstrap
    |
    +--> aplicação inicia
    |
    +--> cfn-signal falha
    |
    v
CloudFormation não recebe sinal
    |
    v
Timeout / rollback
```

## Sugestão

Adicionar uma validação antes do `sam deploy`.

Exemplo conceitual:

```powershell
$Endpoint = aws ec2 describe-vpc-endpoints `
    --filters `
        "Name=vpc-id,Values=$VpcId" `
        "Name=service-name,Values=com.amazonaws.$AwsRegion.cloudformation" `
        "Name=vpc-endpoint-state,Values=available"
```

Se não existir:

```powershell
throw "CloudFormation VPC Endpoint não encontrado."
```

## Outra opção

Criar um stack separado para infraestrutura compartilhada:

```text
loto-bot-network
    |
    +-- VPC
    +-- Subnet
    +-- Internet Gateway
    +-- Route Table
    +-- CloudFormation VPC Endpoint
    +-- Security Groups compartilhados
```

E outro stack:

```text
loto-bot
    |
    +-- EC2
    +-- IAM
    +-- aplicação
```

---

# 6. Automatizar teste do túnel SOCKS5

A branch já possui uma boa estratégia de **fail-closed**.

O comportamento desejado é:

```text
Túnel ativo
    |
    v
Chromium acessa CAIXA
```

e:

```text
Túnel desligado
    |
    v
Chromium NÃO deve acessar CAIXA
```

## Sugestão

Criar um script independente:

```text
scripts/test-socks5-tunnel.ps1
```

Responsável por verificar:

1. processo SSH ativo;
2. listener `127.0.0.1:1080` presente na EC2;
3. saída HTTP pelo SOCKS5;
4. carregamento da página CAIXA;
5. encerramento controlado do túnel;
6. validação fail-closed.

Exemplo de testes:

```bash
ss -lnt | grep 127.0.0.1:1080
```

```bash
curl --socks5-hostname 127.0.0.1:1080 https://api.ipify.org
```

e Playwright:

```python
page.goto(
    "https://www.loteriasonline.caixa.gov.br/silce-web/#/termos-de-uso"
)
```

Validando:

```text
Loterias Online da CAIXA
```

---

# 7. Criar GitHub Actions

Não deve ser necessário depender apenas de testes locais antes de merge.

## Pipeline sugerido

Criar:

```text
.github/workflows/ci.yml
```

Executando:

```text
Checkout
   |
   v
Python 3.12
   |
   v
pip install .[dev]
   |
   +--> pytest
   |
   +--> ruff check .
   |
   +--> ruff format --check .
   |
   +--> sam validate --lint
```

## Exemplo de comandos

```bash
pytest
```

```bash
ruff check .
```

```bash
ruff format --check .
```

```bash
sam validate --lint
```

## Recomendação

Tornar esses checks obrigatórios antes de merge para `main`.

---

# 8. Melhorar diagnóstico do bootstrap da EC2

O bootstrap já grava:

```text
/var/log/loto-bot-bootstrap.log
```

Isso é positivo.

## Sugestão

Adicionar logs de checkpoints claros:

```bash
echo "[01/10] IPv6 ready"
echo "[02/10] Installing OS packages"
echo "[03/10] Installing AWS CLI"
echo "[04/10] Downloading release"
echo "[05/10] Validating SHA256"
echo "[06/10] Installing LotoBot"
echo "[07/10] Installing Chromium"
echo "[08/10] Loading Secrets Manager"
echo "[09/10] Starting systemd services"
echo "[10/10] Health check OK"
```

Isso facilita identificar exatamente onde ocorreu uma falha.

## Comando operacional

```bash
sudo tail -F /var/log/loto-bot-bootstrap.log
```

ou:

```bash
watch -n 5 'sudo tail -n 100 /var/log/loto-bot-bootstrap.log'
```

---

# 9. Adicionar diagnóstico automático em caso de erro

Dentro da função de erro do bootstrap, incluir:

```bash
systemctl status loto-bot --no-pager || true
journalctl -u loto-bot -n 200 --no-pager || true
systemctl status nginx --no-pager || true
ip -6 addr show || true
ip -6 route show || true
ss -lntp || true
```

Assim, o arquivo:

```text
/var/log/loto-bot-bootstrap.log
```

já contém informações suficientes para diagnóstico.

---

# 10. Separar infraestrutura compartilhada

Atualmente algumas dependências são externas ao stack principal.

Uma estrutura mais clara seria:

```text
infra/
├── network/
│   └── template.yaml
│
├── integrations/
│   └── template.yaml
│
└── loto-bot/
    └── template.yaml
```

## `network`

Responsável por:

```text
VPC
Subnet
Internet Gateway
Route Table
CloudFormation Endpoint
Security Groups compartilhados
```

## `integrations`

Responsável por:

```text
Gmail Reader
Mail Sender
WhatsApp Notify
```

## `loto-bot`

Responsável por:

```text
EC2
IAM Instance Role
Secrets
Application Security Group
Bootstrap
```

Isso reduz acoplamento entre aplicação e infraestrutura.

---

# 11. Unificar scripts PowerShell IPv4/IPv6

Existem scripts semelhantes:

```text
start-browser-socks5-ipv4-aws.ps1
start-browser-socks5-ipv6-aws.ps1
start-socks5-ipv4-aws.ps1
stop-socks5-ipv4-aws.ps1
stop-socks5-ipv6-aws.ps1
```

## Sugestão

Extrair funções compartilhadas:

```text
scripts/aws-common.ps1
```

Exemplo:

```powershell
function Invoke-AwsCommand {}
function Wait-SshReady {}
function Save-LotoBotState {}
function New-LotoBotKeyPair {}
function Remove-LotoBotResources {}
function Test-Socks5Listener {}
```

Então os scripts principais ficam menores e mais fáceis de manter.

---

# 12. Tornar o arquivo de estado mais robusto

Atualmente existe um JSON local de estado para permitir cleanup.

Sugestão de estrutura:

```json
{
  "version": 1,
  "status": "ready",
  "awsProfile": "AWSCLI260909",
  "awsRegion": "us-east-1",
  "testId": "lotobot-123",
  "vpcId": "vpc-...",
  "subnetId": "subnet-...",
  "routeTableId": "rtb-...",
  "internetGatewayId": "igw-...",
  "securityGroupId": "sg-...",
  "instanceId": "i-...",
  "publicIpv6": "...",
  "keyFile": "...",
  "knownHostsFile": "...",
  "tunnelProcessId": 12345
}
```

Adicionar:

```text
version
createdAt
updatedAt
status
```

facilita evoluções futuras.

---

# 13. Validar pré-requisitos localmente

Antes de criar qualquer recurso AWS:

```text
AWS CLI
SSH
SCP
curl
PowerShell
perfil AWS
região
credenciais
IPv6 local
```

## Exemplo

```powershell
Get-Command aws -ErrorAction Stop
Get-Command ssh -ErrorAction Stop
Get-Command scp -ErrorAction Stop
Get-Command curl.exe -ErrorAction Stop
```

Validar autenticação:

```powershell
aws sts get-caller-identity @AwsCommon
```

Validar IPv6:

```powershell
curl.exe -6 -fsS https://api64.ipify.org
```

Isso evita criação parcial de recursos antes de descobrir uma falha local.

---

# 14. Validar região e tipo da instância

Criar validações para evitar erros como troca acidental entre:

```text
AwsRegion
InstanceType
```

Exemplo:

```powershell
if ($AwsRegion -notmatch '^[a-z]{2}-[a-z]+-\d+$') {
    throw "Região AWS inválida: $AwsRegion"
}
```

e:

```powershell
$AllowedInstanceTypes = @(
    "t3.micro",
    "t3.small"
)

if ($InstanceType -notin $AllowedInstanceTypes) {
    throw "InstanceType inválido: $InstanceType"
}
```

---

# 15. Melhorar recuperação automática do túnel

Hoje o túnel SSH é crítico:

```text
PC local
   |
   | SSH
   v
EC2 SOCKS5
```

Se ele cair, o Chromium perde acesso externo pela rota esperada.

## Sugestão

No PC local, utilizar um processo supervisor.

Exemplo:

```text
start-lotobot-tunnel.ps1
```

com loop:

```powershell
while ($true) {
    ssh ...
    Start-Sleep -Seconds 5
}
```

ou utilizar:

```text
autossh
```

em ambiente Linux.

## Importante

O restart deve continuar fail-closed.

Nunca deve existir fallback para:

```text
EC2 -> Internet direta
```

quando a intenção for forçar saída pelo proxy local.

---

# 16. Adicionar health check do SOCKS5

Criar um endpoint interno:

```text
GET /health/proxy
```

que verifique apenas disponibilidade técnica do SOCKS5.

Exemplo de resposta:

```json
{
  "status": "UP",
  "proxy": "socks5://127.0.0.1:1080"
}
```

Não é necessário acessar a CAIXA a cada health check.

Pode ser validado:

```text
TCP 127.0.0.1:1080
```

e eventualmente uma URL neutra externa.

---

# 17. Health checks separados

Recomendação:

```text
GET /health
GET /health/browser
GET /health/proxy
GET /health/integrations
```

### `/health`

Aplicação FastAPI.

### `/health/browser`

Processo Chromium / Playwright.

### `/health/proxy`

SOCKS5.

### `/health/integrations`

Acesso ao ambiente AWS interno.

Isso ajuda a identificar rapidamente onde está a falha.

---

# 18. Melhorar hardening do systemd

A configuração atual já utiliza:

```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
```

É uma boa base.

Pode-se avaliar também:

```ini
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
PrivateDevices=true
```

Sempre testando previamente se o Chromium continua funcionando.

---

# 19. Revisar `--no-sandbox`

Atualmente o Chromium utiliza:

```text
--no-sandbox
--disable-setuid-sandbox
```

Essas opções reduzem mecanismos de isolamento do Chromium.

## Sugestão

Testar se o Playwright consegue funcionar como usuário não-root sem:

```text
--no-sandbox
```

Caso seja possível, remover.

Como o serviço já roda com:

```ini
User=loto-bot
```

há boas chances de ser possível configurar o ambiente adequadamente.

---

# 20. Revisar User-Agent fixo

Existe um User-Agent semelhante a:

```text
Chrome/122
```

Como o Playwright instala versões mais recentes do Chromium, isso pode gerar inconsistência:

```text
Chromium real: versão atual
User-Agent: Chrome 122
```

## Sugestão

Utilizar o User-Agent padrão do Chromium, a menos que exista uma necessidade concreta de sobrescrevê-lo.

Alternativamente, gerar dinamicamente a versão.

---

# 21. Secrets Manager

A decisão de guardar:

```text
BETTOR_CPF
BETTOR_PASSWORD
CREDIT_CARD_LAST_DIGITS
CREDIT_CARD_SECURITY_CODE
MAIL_TO
```

no Secrets Manager é adequada.

## Sugestão

Evitar persistir o conteúdo do Secret além do necessário.

O fluxo ideal é:

```text
Secrets Manager
     |
     v
bootstrap
     |
     v
/etc/loto-bot.env
```

Arquivo:

```text
root:root
0600
```

Também é recomendável garantir que:

```text
/etc/loto-bot.env
```

nunca apareça em:

```text
artifact
Git
logs
backup público
```

---

# 22. Não registrar informações sensíveis

Revisar logs para garantir que nunca sejam impressos:

```text
CPF
senha
CVV
token
código de validação completo
conteúdo do Secrets Manager
```

A função:

```python
mask_sensitive_value()
```

deve continuar sendo usada.

Recomendação de mascaramento:

```text
123456 -> ****56
```

---

# 23. IAM Least Privilege

A política atual restringe recursos de:

```text
s3:GetObject
secretsmanager:GetSecretValue
lambda:InvokeFunction
```

Isso deve ser mantido.

Sugestão adicional:

não permitir:

```text
Resource: "*"
```

para essas ações.

Sempre preferir ARNs específicos.

---

# 24. MongoDB

Atualmente:

```text
PERSISTENCE_ENABLED=false
```

é coerente para reduzir custo e complexidade inicialmente.

Caso MongoDB seja habilitado no futuro, evitar instalar banco local automaticamente sem avaliar:

```text
RAM
swap
EBS
backup
persistência
```

Uma `t3.micro` executando:

```text
FastAPI
Chromium
Playwright
Nginx
MongoDB
```

pode ter pressão significativa de memória.

---

# 25. Swap

O bootstrap cria:

```text
2 GB swap
```

Isso é útil para Chromium em instância pequena.

Sugestão:

monitorar:

```bash
free -h
```

```bash
vmstat
```

```bash
swapon --show
```

Caso haja uso constante de swap, considerar:

```text
t3.small
```

em vez de aumentar excessivamente o swap.

---

# 26. Monitorar créditos de CPU

A configuração usa:

```yaml
CPUCredits: standard
```

Essa é uma boa escolha para evitar cobrança inesperada de Unlimited CPU Credits.

Monitorar:

```text
CPUCreditBalance
CPUUtilization
```

principalmente durante:

```text
instalação do Chromium
execução do Playwright
fluxo de aposta
```

---

# 27. EBS

O template permite:

```text
16–30 GB gp3
```

Sugestão:

iniciar com o menor tamanho compatível com:

```text
Ubuntu
Python
Playwright
Chromium
logs
perfil persistente
swap
```

Monitorar:

```bash
df -h
```

antes de aumentar.

---

# 28. Cleanup dos recursos temporários

O `stop-socks5-ipv6-aws.ps1` possui uma boa estratégia de cleanup.

Recomendação adicional:

adicionar tags:

```text
Application=loto-bot
Environment=test
CreatedBy=socks5-test
ExpiresAt=<timestamp>
```

Assim é possível detectar recursos temporários esquecidos.

---

# 29. Criar auditoria de recursos esquecidos

Adicionar:

```text
scripts/find-orphan-aws-resources.ps1
```

Buscando recursos com:

```text
Application=loto-bot
```

e exibindo:

```text
EC2
VPC
Subnet
Internet Gateway
Security Group
Key Pair
EBS
VPC Endpoint
```

Isso ajuda a evitar custos inesperados.

---

# 30. Documentar estratégia de acesso

Deixar explícito no README:

## Administração

```text
SSH IPv6
SSM Session Manager
```

## API

```text
SSM Port Forward
```

## Browser

```text
EC2 Chromium
```

## Internet do Chromium

```text
SOCKS5 reverso pelo PC local
```

## Integrações AWS

```text
Lambda Invoke
```

Isso evita confusão entre:

```text
API da aplicação
proxy SOCKS5
SSH
browser
integrações
```

---

# 31. CI recomendado antes do merge

Antes de integrar a branch:

```powershell
pytest
```

```powershell
ruff check .
```

```powershell
ruff format --check .
```

```powershell
sam validate --lint
```

Também testar:

```text
start-browser-socks5-ipv6-aws.ps1
```

e depois:

```text
stop-socks5-ipv6-aws.ps1
```

---

# 32. Teste de homologação recomendado

Executar o fluxo:

```text
1. Criar infraestrutura
2. Subir EC2
3. Confirmar IPv6
4. Confirmar SSH
5. Abrir túnel SOCKS5
6. Confirmar listener 127.0.0.1:1080
7. Executar Chromium
8. Abrir Termos de Uso da CAIXA
9. Validar título da página
10. Executar endpoint /health
11. Testar Gmail Reader
12. Testar Mail Sender
13. Testar API LotoBot
14. Encerrar túnel
15. Confirmar fail-closed
16. Restaurar túnel
17. Confirmar recuperação
18. Executar cleanup
19. Confirmar remoção de todos os recursos temporários
```

---

# 33. Arquitetura recomendada após os ajustes

```text
                    PC LOCAL
                +---------------+
                | SOCKS5 source |
                +-------+-------+
                        |
                        | SSH IPv6 / TCP 22
                        |
                        v
                  AWS EC2 LotoBot
           +---------------------------+
           | FastAPI                   |
           | Playwright                |
           | Chromium                  |
           | 127.0.0.1:1080 SOCKS5    |
           +-----------+---------------+
                       |
        +--------------+--------------+
        |                             |
        | Chromium traffic            | AWS API traffic
        v                             v
   SOCKS5 tunnel                 AWS APIs / Lambda
        |                             |
        v                             +--> Gmail Reader
     PC local                         |
        |                             +--> Mail Sender
        v
    Internet
        |
        v
Loterias Online CAIXA
```

A API LotoBot pode ser acessada administrativamente por:

```text
SSM Port Forward
```

sem precisar deixá-la exposta publicamente.

---

# 34. Ordem recomendada de implementação

## Fase 1 — Correções imediatas

1. revisar/remover `LambdaVpcEndpoint`;
2. corrigir `Security Group 443` x `Nginx 80`;
3. validar endpoint CloudFormation antes do deploy;
4. executar testes completos.

## Fase 2 — Confiabilidade

5. adicionar GitHub Actions;
6. criar health check SOCKS5;
7. adicionar diagnóstico automático;
8. melhorar supervisão/reconexão do túnel.

## Fase 3 — Manutenção

9. separar stacks;
10. refatorar scripts PowerShell;
11. criar auditoria de recursos;
12. melhorar documentação operacional.

## Fase 4 — Hardening

13. revisar sandbox do Chromium;
14. reforçar systemd;
15. revisar User-Agent;
16. revisar logs e secrets.

---

# 35. Conclusão

A branch `AWS_FREE_TIER_MIGRATION` possui uma base arquitetural sólida para o cenário desejado:

```text
LotoBot + Chromium na EC2
PC local como saída SOCKS5
conectividade EC2 via IPv6
integrações AWS desacopladas
```

Os principais pontos a serem tratados antes de consolidar a arquitetura são:

```text
1. custo dos Interface VPC Endpoints;
2. divergência entre porta 443 do Security Group e porta 80 do Nginx;
3. dependência externa do endpoint CloudFormation;
4. ausência de CI automatizado;
5. robustez operacional do túnel SOCKS5.
```

Após esses ajustes, a arquitetura tende a ficar:

```text
mais barata
mais simples
mais segura
mais observável
mais fácil de manter
```
