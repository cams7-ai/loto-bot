# Sugestões de melhorias — `whatsapp-notify`

> **Estado após os ajustes:** a rota de início de sessão aceita `timeoutInSeconds` e mantém `timeoutInSecounds` como alias temporário; o timeout do Nginx foi alinhado ao fluxo. README e guia AWS foram atualizados. O health check e a semântica da sessão permanecem como estavam, conforme solicitado. As seções abaixo registram as sugestões originais e podem descrever o estado anterior.

## 1. Contexto

Repositório:

```text
https://github.com/cams7-ai/whatsapp-notify.git
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
docs/AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md
docs/CREATE_AMI_AND_DEPLOY.md
samconfig.local.toml
template.yaml
template-ami.yaml
tests/test_whatsapp_routes.py
```

A arquitetura proposta utiliza uma instância EC2 persistente para manter a sessão do WhatsApp Web via Chromium/Playwright, com comunicação privada entre LotoBot e WhatsApp Notify.

---

# 2. Arquitetura atual

Fluxo principal:

```text
                   Internet
                      |
                      | IPv6
                      v
                WhatsApp Web
                      ^
                      |
                HTTPS IPv6
                      |
        +-------------+-------------+
        | WhatsApp Notify EC2       |
        |                           |
        | FastAPI :8000             |
        | Nginx :80                 |
        | Chromium + Playwright     |
        | Perfil persistente        |
        +-------------+-------------+
                      ^
                      |
               HTTP privado
                 TCP :80
                      |
          Security Group -> SG
                      |
        +-------------+-------------+
        | LotoBot EC2               |
        +---------------------------+
```

A comunicação LotoBot -> WhatsApp Notify ocorre por rede privada da VPC.

---

# 3. Resumo das prioridades

| Prioridade | Melhoria | Impacto |
|---|---|---|
| P0 | Atualizar `README.md` para a arquitetura atual | Evita deploy seguindo fluxo obsoleto |
| P0 | Decidir se SSM permanece ou será removido | Elimina arquitetura ambígua |
| P1 | Corrigir nomenclatura “IPv6-only” | Melhora precisão arquitetural |
| P1 | Reavaliar CloudFormation Interface Endpoint | Pode reduzir custo |
| P1 | Documentar limites da persistência da sessão | Evita perda inesperada de autenticação |
| P1 | Definir claramente uso de `template.yaml` e `template-ami.yaml` | Simplifica operação |
| P1 | Melhorar diagnóstico de bootstrap | Facilita troubleshooting |
| P2 | Adicionar CI para testes e validação SAM | Evita regressões |
| P2 | Melhorar documentação do `IntegrationSecurityGroupId` | Facilita integração com LotoBot |
| P2 | Avaliar volume EBS separado para perfil WhatsApp | Aumenta resiliência |
| P2 | Revisar regras de egress IPv4 sem rota IPv4 pública | Reduz configuração redundante |
| P3 | Aumentar hardening do systemd | Segurança |
| P3 | Melhorar observabilidade e health checks | Operação |

---

# 4. Atualizar `README.md`

## Problema

O README ainda descreve elementos da arquitetura anterior, como:

```text
AWS Systems Manager Session Manager
Budgets
port forwarding via SSM
```

Enquanto a branch atual utiliza principalmente:

```text
SSH IPv6 restrito
VPC compartilhada
HTTP privado entre LotoBot e WhatsApp Notify
```

Isso cria duas versões diferentes da arquitetura dentro do mesmo projeto.

## Sugestão

Atualizar:

```text
README.md
```

para refletir exatamente a branch atual.

Remover ou corrigir referências a:

```text
Budget criado pelo template
SSM como método principal de acesso
SSM port forwarding como fluxo padrão
```

Documentar:

```text
Administração:
SSH IPv6 restrito

Comunicação LotoBot -> WhatsApp Notify:
HTTP privado TCP/80

Internet do Chromium:
IPv6

IPv4 público:
não utilizado
```

---

# 5. Decidir definitivamente sobre SSM

## Problema

A branch indica que o acesso administrativo foi migrado para:

```text
SSH IPv6
```

Porém os templates ainda possuem:

```yaml
ManagedPolicyArns:
  - arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
```

e:

```yaml
SessionManagerCommand:
```

Isso torna a arquitetura inconsistente.

## Opção A — remover SSM

Se SSH IPv6 é o método oficial:

remover:

```text
AmazonSSMManagedInstanceCore
SessionManagerCommand
referências ao SSM na documentação
```

Benefícios:

```text
IAM menor
menos dependências
menos ambiguidades
```

## Opção B — manter como fallback

Se SSM deve permanecer como fallback:

documentar explicitamente:

```text
SSH IPv6 = acesso principal
SSM = acesso alternativo de recuperação
```

Também validar que o ambiente possui conectividade necessária aos endpoints do SSM.

---

# 6. Corrigir o termo “IPv6-only”

## Problema

A arquitetura não é realmente IPv6-only.

A EC2 possui:

```text
IPv4 privado da VPC
IPv6 público
```

A comunicação com o LotoBot utiliza IPv4 privado.

## Sugestão

Substituir termos como:

```text
IPv6-only EC2
```

por:

```text
EC2 sem IPv4 público
```

ou:

```text
EC2 dual-stack com IPv4 privado e IPv6 público
```

Arquitetura real:

```text
LotoBot
   |
   | IPv4 privado
   v
WhatsApp Notify
   |
   | IPv6
   v
Internet / WhatsApp Web
```

---

# 7. Reavaliar o CloudFormation Interface Endpoint

## Situação atual

Os templates assumem que a VPC compartilhada possui previamente:

```text
CloudFormation Interface VPC Endpoint
PrivateDnsEnabled=true
```

para permitir:

```text
cfn-signal
```

## Problema

Interface VPC Endpoint é um recurso que pode gerar custo contínuo.

Isso deve ser analisado porque a branch tem objetivo de reduzir custos AWS.

## Sugestão

Verificar se:

```text
cfn-signal
```

pode utilizar o endpoint público regional via IPv6/dual-stack.

Se funcionar de maneira confiável, avaliar remoção da dependência do endpoint privado.

Fluxo simplificado:

```text
EC2
 |
 | HTTPS IPv6
 v
CloudFormation regional endpoint
```

Caso o endpoint privado permaneça, documentar claramente:

```text
é infraestrutura compartilhada
possui custo próprio
não pertence exclusivamente ao whatsapp-notify
```

---

# 8. Documentar corretamente a persistência da sessão

## Situação atual

O perfil é armazenado em:

```text
/opt/whatsapp-notify/data/.whatsapp-profile
```

e o serviço utiliza uma EC2 persistente.

Isso preserva a sessão durante:

```text
restart da aplicação
restart do Chromium
reboot da EC2
```

## Limitação

O volume raiz possui:

```yaml
DeleteOnTermination: true
```

Portanto, em uma substituição da EC2:

```text
EC2 substituída
      |
      v
volume raiz removido
      |
      v
.whatsapp-profile perdido
      |
      v
nova autenticação por QR Code
```

## Sugestão

Documentar explicitamente:

```text
Persistência durante a vida da EC2: SIM
Persistência entre substituições da EC2: NÃO
```

---

# 9. Avaliar EBS separado para o perfil WhatsApp

Se for importante preservar a sessão mesmo quando a EC2 for substituída, considerar:

```text
Volume EBS raiz
  |
  +-- sistema operacional
  +-- aplicação

Volume EBS de dados
  |
  +-- /opt/whatsapp-notify/data
      |
      +-- .whatsapp-profile
```

Benefícios:

```text
perfil independente da instância
rollback mais simples
substituição da EC2 sem perder sessão
backup mais simples
```

## Atenção

O perfil do WhatsApp contém dados de autenticação sensíveis.

O volume deve permanecer:

```text
criptografado
sem compartilhamento
com backup controlado
```

---

# 10. Definir claramente `template.yaml` x `template-ami.yaml`

Existem atualmente dois fluxos.

## `template.yaml`

Executa bootstrap completo:

```text
instala pacotes
instala AWS CLI
baixa artifact
valida SHA256
cria venv
pip install
instala Playwright
instala Chromium
cria systemd
configura Nginx
```

## `template-ami.yaml`

Assume aplicação pré-instalada:

```text
AMI pronta
      |
      v
valida executáveis
      |
      v
inicia serviços
      |
      v
health check
```

## Sugestão

Documentar oficialmente:

| Template | Finalidade |
|---|---|
| `template.yaml` | Bootstrap inicial / construção da instância base |
| `template-ami.yaml` | Deploy normal, atualização e rollback |

Fluxo recomendado:

```text
template.yaml
     |
     v
instância validada
     |
     v
criar AMI
     |
     v
template-ami.yaml
     |
     v
deploys subsequentes
```

---

# 11. Melhorar o bootstrap

O bootstrap já possui:

```text
set -euo pipefail
log em arquivo
trap de falha
health check
cfn-signal
```

Esses são bons fundamentos.

## Sugestão

Adicionar checkpoints:

```bash
echo "[01/10] IPv6 ready"
echo "[02/10] Installing OS dependencies"
echo "[03/10] Installing AWS CLI"
echo "[04/10] Downloading artifact"
echo "[05/10] Verifying SHA256"
echo "[06/10] Installing application"
echo "[07/10] Installing Chromium"
echo "[08/10] Configuring systemd"
echo "[09/10] Configuring nginx"
echo "[10/10] Health check OK"
```

Isso facilita identificar rapidamente onde ocorreu a falha.

---

# 12. Melhorar diagnóstico automático

Na função de falha do bootstrap, registrar:

```bash
systemctl status whatsapp-notify --no-pager || true
journalctl -u whatsapp-notify -n 200 --no-pager || true
systemctl status nginx --no-pager || true
nginx -t || true
ip addr show || true
ip -6 route show || true
ss -lntp || true
df -h || true
free -h || true
```

Assim:

```text
/var/log/whatsapp-notify-bootstrap.log
```

fica mais útil para análise remota.

---

# 13. Melhorar health checks

Atualmente:

```text
/whatsapp/session/status
```

é utilizado para verificar se a aplicação iniciou.

Isso funciona, mas mistura:

```text
saúde da API
estado funcional da sessão WhatsApp
```

## Sugestão

Adicionar:

```text
GET /health
```

Resposta simples:

```json
{
  "status": "UP"
}
```

Então usar:

```bash
curl http://127.0.0.1:8000/health
```

no bootstrap.

Manter:

```text
/whatsapp/session/status
```

para estado funcional.

---

# 14. Health checks separados

Uma evolução possível:

```text
GET /health
GET /health/browser
GET /whatsapp/session/status
```

### `/health`

Processo FastAPI ativo.

### `/health/browser`

Chromium/Playwright tecnicamente disponível.

### `/whatsapp/session/status`

Estado da sessão do WhatsApp.

Isso melhora troubleshooting.

---

# 15. Comunicação privada com LotoBot

Esta parte da arquitetura está boa e deve ser preservada.

O Security Group permite:

```yaml
SourceSecurityGroupId: !Ref IntegrationSecurityGroupId
```

Resultado:

```text
LotoBot Security Group
        |
        | TCP/80
        v
WhatsApp Notify Security Group
```

## Sugestão

Melhorar a descrição do parâmetro:

```text
IntegrationSecurityGroupId
```

para deixar explícito que ele representa:

```text
o Security Group anexado ao LotoBot consumidor
```

e não um Security Group pertencente ao próprio WhatsApp Notify.

---

# 16. `ApiUrl`

O output atual:

```yaml
ApiUrl:
  Value: !Sub "http://${ApplicationInstance.PrivateDnsName}"
```

é adequado para comunicação privada.

O fluxo esperado deve ser documentado:

```text
Deploy WhatsApp Notify
       |
       v
Output ApiUrl
       |
       v
WHATSAPP_NOTIFY_URL no LotoBot
```

Exemplo:

```text
WHATSAPP_NOTIFY_URL=http://ip-10-x-x-x.ec2.internal
```

---

# 17. Revisar egress IPv4

O Security Group permite:

```text
0.0.0.0/0 TCP 80
0.0.0.0/0 TCP 443
0.0.0.0/0 DNS
```

mas a arquitetura pretende não possuir rota de Internet IPv4 pública.

Essas regras não necessariamente geram acesso, mas podem confundir.

## Sugestão

Revisar se são necessárias para:

```text
comunicação privada AWS
integrações na VPC
DNS
```

e documentar o motivo.

Se não forem necessárias, remover regras redundantes.

---

# 18. Hardening do systemd

Já existem:

```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
```

Boa base.

## Sugestão

Avaliar também:

```ini
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
PrivateDevices=true
```

Adicionar uma por vez e testar Playwright/Chromium.

---

# 19. Revisar sandbox do Chromium

Se houver uso de:

```text
--no-sandbox
--disable-setuid-sandbox
```

avaliar se ainda são necessários executando a aplicação como:

```text
User=whatsapp-notify
```

Caso Chromium funcione sem essas opções, removê-las.

Isso melhora isolamento.

---

# 20. Gestão do perfil WhatsApp

O perfil:

```text
.whatsapp-profile
```

deve continuar excluído de:

```text
Git
artifact ZIP
AMI sanitizada
logs
backup público
```

## Sugestão

Adicionar verificações automáticas antes de gerar artifact:

```text
falhar se .whatsapp-profile estiver presente
falhar se .env estiver presente
falhar se arquivos *.pem / *.key estiverem presentes
```

---

# 21. AMI sanitizada

A documentação de criação da AMI já possui uma boa abordagem de limpeza.

Reforçar como requisito:

```text
não incluir sessão WhatsApp autenticada
não incluir .env
não incluir PEM
não incluir chaves privadas
não incluir histórico de shell sensível
regenerar SSH host keys
```

A regra principal deve ser:

```text
AMI contém software
AMI não contém identidade/autenticação
```

---

# 22. Backup e rollback

Definir duas coisas separadamente:

```text
rollback da aplicação
rollback da sessão
```

Rollback da aplicação:

```text
AMI anterior
```

Rollback da sessão:

```text
perfil WhatsApp persistente
```

Atualmente são problemas diferentes.

Documentar explicitamente isso evita assumir que reverter AMI também recupera sessão.

---

# 23. Testes automatizados

As alterações em:

```text
tests/test_whatsapp_routes.py
```

melhoraram a validação do contrato.

Foram adicionados testes para:

```text
rota antiga /notifications inexistente
/send-and-close inexistente
payload headless rejeitado
charset UTF-8
delegação correta ao handler
```

Isso deve ser mantido.

---

# 24. Adicionar CI

A branch atualmente não apresenta workflow/status checks associados ao HEAD.

## Sugestão

Criar:

```text
.github/workflows/ci.yml
```

Executando:

```text
pytest
sam validate --lint --template-file template.yaml
sam validate --lint --template-file template-ami.yaml
```

Se o projeto utilizar Ruff:

```text
ruff check .
ruff format --check .
```

Fluxo:

```text
push / pull request
        |
        +--> testes
        +--> lint
        +--> template.yaml
        +--> template-ami.yaml
```

---

# 25. Proteção da branch

Atualmente a branch:

```text
AWS_FREE_TIER_MIGRATION
```

não possui required status checks.

Após criar CI, considerar exigir checks antes de merge para:

```text
main
```

Principalmente:

```text
pytest
SAM lint
```

---

# 26. `samconfig.local.toml`

O arquivo está coerente com os parâmetros atuais:

```text
VpcId
SubnetId
AmiId
InstanceType
KeyName
AllowedSshIpv6Cidr
IntegrationSecurityGroupId
ArtifactBucket
ArtifactKey
ArtifactSha256
RootVolumeSize
```

## Sugestão

Manter:

```text
samconfig.local.toml
```

sem dados sensíveis.

Nunca incluir:

```text
tokens
senha
CPF
credenciais do WhatsApp
PEM
secret values
```

---

# 27. SSH IPv6

A regra:

```text
AllowedSshIpv6Cidr=/128
```

é adequada.

Preservar:

```text
nunca ::/0
```

## Sugestão

Adicionar validação no guia antes do deploy:

```powershell
$PublicIpv6 = curl.exe -6 -fsS https://api64.ipify.org

$AllowedSshIpv6Cidr = "$PublicIpv6/128"
```

E validar:

```text
IPv6 válido
/128
```

antes de enviar ao SAM.

---

# 28. Rotação de IPv6 local

Como o SSH depende do IPv6 público do computador autorizado, documentar procedimento para:

```text
IPv6 local mudou
```

Fluxo:

```text
obter novo IPv6
      |
      v
atualizar AllowedSshIpv6Cidr
      |
      v
sam deploy
      |
      v
SSH liberado novamente
```

Isso deve estar no troubleshooting.

---

# 29. Logs

Manter:

```text
LOG_LEVEL=INFO
```

por padrão.

Usar:

```text
DEBUG
```

somente temporariamente.

## Sugestão

Garantir que logs nunca incluam:

```text
QR code em Base64
cookies
localStorage
tokens
dados de sessão WhatsApp
conteúdo sensível do perfil
```

---

# 30. Monitoramento de recursos

Uma `t3.micro` executando:

```text
FastAPI
Nginx
Chromium
Playwright
```

pode ficar limitada.

Monitorar:

```bash
free -h
vmstat
df -h
top
```

Na AWS, acompanhar:

```text
CPUUtilization
CPUCreditBalance
StatusCheckFailed
```

---

# 31. Swap

A criação de:

```text
2 GB de swap
```

é adequada para reduzir risco de OOM em instância pequena.

Porém swap deve ser tratado como proteção, não como solução para pressão contínua de memória.

Se houver uso constante:

```text
t3.small
```

pode ser mais adequado.

---

# 32. `CPUCredits: standard`

Manter:

```yaml
CreditSpecification:
  CPUCredits: standard
```

Isso ajuda a evitar cobrança inesperada associada ao modo Unlimited.

---

# 33. Nginx

A arquitetura:

```text
Nginx :80
   |
   v
FastAPI 127.0.0.1:8000
```

está coerente.

Como a comunicação é privada e controlada por Security Group, HTTP interno pode ser aceitável para este cenário.

Se no futuro houver tráfego fora da VPC:

```text
não expor porta 80 diretamente
```

e considerar TLS.

---

# 34. Timeout do Nginx

Atualmente existe:

```nginx
proxy_read_timeout 90s;
proxy_send_timeout 90s;
```

Isso é razoável porque operações com WhatsApp Web podem demorar.

Sugestão:

alinhar esses timeouts com:

```text
WHATSAPP_TIMEOUT_SECONDS
```

para evitar:

```text
aplicação ainda processando
Nginx já encerrou a conexão
```

---

# 35. QR Code

O endpoint:

```text
/whatsapp/session/qrcode
```

retorna material de autenticação sensível.

Mesmo dentro da infraestrutura administrativa, tratar QR Code como secreto de curta duração.

## Sugestão

Manter:

```text
Cache-Control: no-store
```

e evitar logs do conteúdo.

---

# 36. Endpoint `/health`

Adicionar endpoint simples pode permitir que:

```text
CloudFormation bootstrap
monitoramento
smoke tests
```

não dependam do estado do WhatsApp.

Exemplo:

```python
@app.get("/health")
def health():
    return {"status": "UP"}
```

---

# 37. Melhorar documentação do primeiro login

O fluxo de primeira autenticação deve ficar extremamente claro:

```text
iniciar sessão
      |
      v
obter QR Code
      |
      v
copiar/visualizar QR Code
      |
      v
escanear no celular
      |
      v
validar SESSION_OPEN
```

Isso é especialmente importante quando:

```text
WHATSAPP_HEADLESS=true
```

na EC2.

---

# 38. Separar deploy de construção de AMI

O guia deve deixar claro que construir uma AMI é uma operação administrativa diferente de fazer deploy.

```text
Build AMI
   |
   +--> preparar
   +--> testar
   +--> sanitizar
   +--> criar imagem

Deploy AMI
   |
   +--> template-ami.yaml
```

Isso reduz risco de produzir uma AMI sem sanitização.

---

# 39. Evitar AMIs antigas acumuladas

AMIs e snapshots antigos podem gerar custo.

Criar procedimento periódico para listar:

```powershell
aws ec2 describe-images
```

e snapshots relacionados.

Não apagar automaticamente.

Sempre validar:

```text
não está em uso
não é rollback ativo
```

antes da exclusão.

---

# 40. Arquitetura recomendada

```text
                         Internet
                            |
                            | IPv6
                            v
                     WhatsApp Web
                            ^
                            |
                      Chromium
                            |
                 +----------+----------+
                 | WhatsApp Notify EC2 |
                 |                     |
                 | FastAPI             |
                 | Nginx               |
                 | Playwright          |
                 +----------+----------+
                            ^
                            |
                     HTTP privado
                       TCP/80
                            |
                 Security Group
                            ^
                            |
                      LotoBot EC2
```

Administração:

```text
PC autorizado
      |
      | SSH IPv6 /128
      v
WhatsApp Notify EC2
```

---

# 41. Ordem recomendada das melhorias

## Fase 1 — Consistência

1. atualizar `README.md`;
2. decidir SSM vs SSH;
3. corrigir nomenclatura IPv6-only;
4. alinhar documentação com templates.

## Fase 2 — Custo e infraestrutura

5. revisar CloudFormation Interface Endpoint;
6. revisar regras egress IPv4;
7. revisar lifecycle de AMIs/snapshots.

## Fase 3 — Resiliência

8. documentar persistência da sessão;
9. avaliar EBS separado;
10. melhorar health checks;
11. melhorar diagnóstico do bootstrap.

## Fase 4 — Qualidade

12. adicionar CI;
13. validar os dois templates;
14. exigir checks antes de merge.

## Fase 5 — Segurança

15. reforçar systemd;
16. revisar sandbox do Chromium;
17. reforçar proteção do QR Code e perfil;
18. revisar logs.

---

# 42. Checklist antes do merge

Executar:

```text
pytest
```

Validar:

```text
template.yaml
template-ami.yaml
```

com:

```powershell
sam validate --lint --template-file template.yaml
sam validate --lint --template-file template-ami.yaml
```

Validar arquitetura real:

```text
1. EC2 sem IPv4 público
2. IPv6 funcional
3. SSH /128 funcional
4. Nginx disponível internamente
5. LotoBot consegue acessar ApiUrl
6. sessão WhatsApp inicia
7. QR Code funciona
8. mensagem é enviada
9. reboot preserva sessão
10. substituição da EC2 exige nova sessão, se perfil continuar no root EBS
```

---

# 43. Conclusão

A branch `AWS_FREE_TIER_MIGRATION` possui uma boa base para o cenário:

```text
LotoBot
   |
   | rede privada
   v
WhatsApp Notify
   |
   | IPv6
   v
WhatsApp Web
```

Os pontos mais importantes antes de consolidar a branch são:

```text
1. alinhar README e documentação com a arquitetura real;
2. decidir definitivamente se SSM permanece;
3. corrigir o conceito de “IPv6-only”;
4. reavaliar o custo do CloudFormation Interface Endpoint;
5. esclarecer o limite da persistência do perfil WhatsApp;
6. adicionar validação automatizada dos templates e testes.
```

Após esses ajustes, o projeto tende a ficar:

```text
mais coerente
mais barato
mais seguro
mais previsível
mais fácil de operar
```
