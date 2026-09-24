# Migração do `loto-bot` para AWS

Este guia descreve a arquitetura vigente do `loto-bot` e deve ser usado junto com o [`template.yaml`](../template.yaml). A integração não utiliza API Gateway nem chave de API.

## 1. Arquitetura

O `loto-bot` é executado em uma única instância EC2 para preservar o processo do Chromium e o perfil persistente do Playwright. As integrações são:

- `mail-sender-aws`: invocação direta da Lambda pelo SDK AWS;
- `gmail-reader-aws`: invocação direta da Lambda pelo SDK AWS;
- `whatsapp-notify`: HTTP privado na porta 80, dentro da VPC;
- portal CAIXA e repositórios de sistema: saída pela internet;
- administração: AWS Systems Manager Session Manager e túnel de porta.

O seletor `INTEGRATION_MODE` aceita somente `LOCAL` ou `AWS`. Use `LOCAL` no desenvolvimento para chamar `GMAIL_READER_URL` e `MAIL_SENDER_URL` por HTTP. O template desta stack sempre grava `INTEGRATION_MODE=AWS`, usando `GMAIL_READER_FUNCTION_NAME` e `MAIL_SENDER_FUNCTION_NAME` para invocação direta.

As chamadas às Lambdas usam o endpoint de interface `com.amazonaws.<região>.lambda`, com DNS privado habilitado. O tráfego permanece na rede AWS, embora o protocolo do SDK para o serviço Lambda continue sendo HTTPS. O WhatsApp usa HTTP porque o tráfego é restrito por Security Group.

Não configure `X-API-Key`, `INTEGRATION_API_TOKEN` ou segredo compartilhado entre aplicações. A autorização das Lambdas é feita por IAM; o acesso ao WhatsApp é feito por Security Group.

> O endpoint de interface do AWS PrivateLink possui cobrança por hora e por volume e não faz parte da franquia gratuita tradicional. Consulte o preço da região antes do deploy.

## 2. Pré-requisitos

- AWS CLI e AWS SAM CLI instalados;
- credenciais AWS válidas e Python 3.12;
- uma VPC e uma subnet com saída para internet;
- um Security Group de integração independente, criado antes das duas stacks EC2;
- stacks `mail-sender-aws` e `gmail-reader-aws` implantadas;
- bucket S3 privado para os artefatos;
- segredo no Secrets Manager para os dados do `loto-bot`;
- permissões para CloudFormation, EC2, IAM, S3, SSM, Secrets Manager e VPC Endpoint.

```powershell
$AwsProfile = "<perfil>"
$AwsRegion = "us-east-1"
$StackName = "loto-bot"
$VpcId = "<vpc-id>"
$SubnetId = "<subnet-id>"
$AmiId = "<ami-ubuntu-compativel-com-python-3.12>"
$ArtifactBucket = "<bucket-privado>"
$Version = "0.1.0"
```

Use a mesma VPC para `loto-bot` e `whatsapp-notify`. A subnet precisa resolver DNS privado e alcançar a internet, diretamente ou por NAT conforme a topologia escolhida.

## 3. Criar o Security Group de integração

Crie o grupo fora das stacks de aplicação para que nenhuma delas dependa da outra. Ele não precisa de regras de entrada: será anexado ao `loto-bot` como identidade de origem e referenciado pelo `whatsapp-notify` em sua regra de entrada.

```powershell
$SecurityGroupName = "lotobot-internal-integration"
$SecurityGroupId = aws ec2 create-security-group `
  --group-name $SecurityGroupName `
  --description "Shared source identity for LotoBot internal integrations" `
  --vpc-id $VpcId `
  --query GroupId --output text `
  --region $AwsRegion --profile $AwsProfile

aws ec2 create-tags `
  --resources $SecurityGroupId `
  --tags Key=Application,Value=lotobot Key=Purpose,Value=internal-integration `
  --region $AwsRegion --profile $AwsProfile
```

Não adicione regras de entrada nem anexe esse grupo à EC2 do `loto-bot`. Caso ele já exista, recupere-o pela VPC e pelo nome:

```powershell
$SecurityGroupId = aws ec2 describe-security-groups `
  --filters "Name=vpc-id,Values=$VpcId" "Name=group-name,Values=$SecurityGroupName" `
  --query "SecurityGroups[0].GroupId" --output text `
  --region $AwsRegion --profile $AwsProfile
```

Guarde o ID para os dois deploys. Não abra portas públicas nesse grupo e não o remova enquanto qualquer uma das stacks o estiver usando.

## 4. Segredo da aplicação

Crie um arquivo local `application-secret.json` que não será versionado:

```json
{
  "bettor_cpf": "<cpf>",
  "bettor_password": "<senha>",
  "credit_card_last_digits": "<ultimos-digitos>",
  "credit_card_security_code": "<codigo-seguranca>",
  "mail_to": "<destinatario>"
}
```

```powershell
$ApplicationSecretArn = aws secretsmanager create-secret `
  --name loto-bot/application `
  --secret-string file://application-secret.json `
  --query ARN --output text `
  --region $AwsRegion --profile $AwsProfile
```

Se o segredo já existir, obtenha seu ARN em vez de criá-lo novamente.

## 5. Obter os ARNs das Lambdas

```powershell
$GmailReaderFunctionArn = aws cloudformation describe-stacks `
  --stack-name gmail-reader `
  --query "Stacks[0].Outputs[?OutputKey=='FunctionArn'].OutputValue | [0]" `
  --output text --region $AwsRegion --profile $AwsProfile

$MailSenderFunctionArn = aws cloudformation describe-stacks `
  --stack-name mail-sender `
  --query "Stacks[0].Outputs[?OutputKey=='FunctionArn'].OutputValue | [0]" `
  --output text --region $AwsRegion --profile $AwsProfile
```

Esses valores são ARNs de função, não URLs. O bootstrap grava `INTEGRATION_MODE=AWS`, `GMAIL_READER_FUNCTION_NAME` e `MAIL_SENDER_FUNCTION_NAME`. As variáveis `GMAIL_READER_URL` e `MAIL_SENDER_URL` são ignoradas nesse modo.

## 6. Publicar o artefato

O ZIP deve conter `pyproject.toml`, `src/` e os demais arquivos versionados na raiz. `git archive` evita incluir `.venv`, perfis do navegador e segredos locais.

```powershell
$ArtifactKey = "loto-bot/releases/$Version/loto-bot.zip"
$ArtifactFile = Join-Path $PWD "loto-bot-$Version.zip"
git archive --format=zip --output=$ArtifactFile HEAD
$ArtifactSha256 = (Get-FileHash $ArtifactFile -Algorithm SHA256).Hash.ToLowerInvariant()
aws s3 cp $ArtifactFile "s3://$ArtifactBucket/$ArtifactKey" --region $AwsRegion --profile $AwsProfile
```

## 7. Implantar o `whatsapp-notify`

Siga o guia do projeto `whatsapp-notify`, usando a mesma VPC, uma subnet com conectividade entre as instâncias e `IntegrationSecurityGroupId=$SecurityGroupId`. Esse deploy não depende da existência da stack do `loto-bot`.

```powershell
$WhatsAppNotifyUrl = aws cloudformation describe-stacks `
  --stack-name whatsapp-notify `
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]" `
  --output text --region $AwsRegion --profile $AwsProfile
```

O valor deve começar com `http://` e apontar para o DNS privado da EC2.

## 8. Implantar o `loto-bot`

```powershell
sam validate --lint --template-file template.yaml
sam deploy `
  --template-file template.yaml `
  --stack-name $StackName `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --region $AwsRegion `
  --profile $AwsProfile `
  --parameter-overrides `
    VpcId=$VpcId SubnetId=$SubnetId AmiId=$AmiId `
    InstanceType=t3.small AllowedCidr=0.0.0.0/32 `
    ArtifactBucket=$ArtifactBucket ArtifactKey=$ArtifactKey ArtifactSha256=$ArtifactSha256 `
    ApplicationSecretArn=$ApplicationSecretArn `
    GmailReaderFunctionArn=$GmailReaderFunctionArn `
    MailSenderFunctionArn=$MailSenderFunctionArn `
    WhatsAppNotifyUrl=$WhatsAppNotifyUrl `
    IntegrationSecurityGroupId=$SecurityGroupId `
    ConfirmPayment=false DynamoDbTableName=loto-bot-bets RootVolumeSize=20
```

Mantenha `ConfirmPayment=false` até concluir os testes controlados. `AllowedCidr=0.0.0.0/32` mantém o acesso externo fechado e usa somente SSM. O template anexa à EC2 tanto seu Security Group de aplicação quanto o grupo externo de integração.

## 9. Validação operacional

```powershell
$InstanceId = aws cloudformation describe-stacks `
  --stack-name $StackName `
  --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue | [0]" `
  --output text --region $AwsRegion --profile $AwsProfile
aws ssm start-session --target $InstanceId --region $AwsRegion --profile $AwsProfile
```

Na instância:

```bash
sudo systemctl status loto-bot --no-pager
sudo journalctl -u loto-bot -n 100 --no-pager
curl -fsS http://127.0.0.1:8000/health
curl -fsS "$WHATSAPP_NOTIFY_URL/whatsapp/session/status"
```

Para acesso local, execute o output `PortForwardCommand` e use `http://127.0.0.1:8080`. Nenhum cabeçalho de chave de API é necessário nas chamadas internas.

Confirme que a role limita `lambda:InvokeFunction` aos dois ARNs, `secretsmanager:GetSecretValue` ao segredo da aplicação e `s3:GetObject` a `loto-bot/releases/*`.

## 10. Atualizações e rollback

Para uma nova versão, execute os testes, gere outro ZIP e SHA-256, envie-o para uma chave S3 versionada, faça deploy e revise o change set. O código e o ambiente são instalados pelo User Data; uma simples alteração de parâmetro não reexecuta o script em uma EC2 existente.

Para rollback, reaplique o `ArtifactKey` e o `ArtifactSha256` anteriores e substitua a instância de forma controlada. O perfil do navegador está no volume raiz e será perdido se a instância for substituída; planeje nova autenticação.

## 11. Custos

- confira EC2, EBS, transferência, S3, Secrets Manager e CloudWatch Logs;
- monitore créditos de CPU das instâncias T;
- o VPC Endpoint de interface para Lambda gera cobrança contínua;
- `t3.small` e volumes acima da franquia podem gerar custo;
- configure AWS Budgets e alertas antes do deploy.

## 12. Checklist

- [ ] Outputs `FunctionArn` das duas Lambdas obtidos.
- [ ] `INTEGRATION_MODE=AWS` no ambiente implantado.
- [ ] Artefato versionado no S3 e SHA-256 conferido.
- [ ] Segredo contém somente as cinco chaves esperadas.
- [ ] `ConfirmPayment=false` no primeiro deploy.
- [ ] Role limitada aos recursos necessários.
- [ ] VPC Endpoint Lambda com DNS privado habilitado.
- [ ] Security Group de integração criado fora das stacks e informado nos dois deploys.
- [ ] WhatsApp aceita porta 80 somente do Security Group de integração.
- [ ] `WHATSAPP_NOTIFY_URL` usa DNS privado e HTTP.
- [ ] Nenhuma variável ou chamada usa chave de API compartilhada.
- [ ] Serviços validados via SSM.
- [ ] Orçamento e alertas configurados.
