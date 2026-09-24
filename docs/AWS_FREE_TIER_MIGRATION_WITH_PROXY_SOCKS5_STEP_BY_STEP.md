# Migração do `loto-bot` para AWS Free Tier com Chromium e proxy SOCKS5 local

Este guia descreve a arquitetura vigente do `loto-bot` e deve ser usado junto com o [`template.yaml`](../template.yaml). A integração não utiliza API Gateway nem chave de API.

## 1. Arquitetura

O `loto-bot` é executado em uma única instância EC2 para preservar o processo do Chromium e o perfil persistente do Playwright. O Chromium usa `socks5://127.0.0.1:1080`, encaminhado por um túnel SSH reverso para um proxy SOCKS5 na máquina local. As integrações são:

- `mail-sender-aws`: Lambda na mesma VPC/subnet dual-stack, invocada diretamente pelo SDK AWS;
- `gmail-reader-aws`: Lambda na mesma VPC/subnet dual-stack, invocada diretamente pelo SDK AWS;
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
- disponibilidade para criar a VPC e a subnet dual-stack descritas nas etapas 3 e 4;
- um Security Group de integração independente, criado antes das duas stacks EC2;
- projetos `mail-sender-aws` e `gmail-reader-aws` disponíveis localmente para implantação depois da criação da rede;
- bucket S3 privado para os artefatos;
- segredo no Secrets Manager para os dados do `loto-bot`;
- permissões para CloudFormation, EC2, IAM, S3, SSM, Secrets Manager e VPC Endpoint.

```powershell
$AwsProfile = "<perfil>"
$AwsRegion = "us-east-1"
$AwsCommon = @("--region", $AwsRegion, "--profile", $AwsProfile)
$AppName = "loto-bot"
$StackName = $AppName
$InstanceType = "t3.micro"
$RemoteUser = "ubuntu"
$KeyName = $StackName
$KeyFile = Join-Path $HOME ".ssh\$KeyName.pem"
$KnownHostsFile = Join-Path $HOME ".ssh\$KeyName-known-hosts"
$SshOptions = @(
  "-6",
  "-i", $KeyFile,
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "UserKnownHostsFile=$KnownHostsFile",
  "-o", "ConnectTimeout=15"
)
$LocalPublicIpv6 = (curl.exe -6 -fsS https://api64.ipify.org).Trim()
$AllowedSshIpv6Cidr = "$LocalPublicIpv6/128"
$OAuthSecretName = "$StackName/application"
$ApplicationSecretPath = "file://application-secret.json"
$AmiId = aws ssm get-parameter --name "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id" --query "Parameter.Value" --output text --region $AwsRegion --profile $AwsProfile
$AccountId = aws sts get-caller-identity --query Account --output text --profile $AwsProfile
$ArtifactBucket = "$StackName-artifacts-$AccountId-$AwsRegion"
```

As próximas etapas criam `$VpcId` e `$SubnetId`. Use essa mesma VPC e subnet para
`loto-bot`, `mail-sender-aws`, `gmail-reader-aws` e `whatsapp-notify`. A subnet será dual-stack para preservar a
comunicação privada IPv4 entre as aplicações, mas a EC2 do `loto-bot` não
receberá IPv4 público; o acesso SSH do fluxo SOCKS5 usará IPv6 público.

## 3. Criar a VPC e associar IPv6

Defina os nomes e obtenha o IPv6 público da máquina que manterá o túnel:

```powershell
$VpcIpv4Cidr = "10.77.0.0/16"
$SubnetIpv4Cidr = "10.77.1.0/24"
```

Crie a VPC solicitando à AWS um bloco IPv6 e aguarde sua disponibilidade:

```powershell
$VpcId = aws ec2 create-vpc `
  --cidr-block $VpcIpv4Cidr `
  --amazon-provided-ipv6-cidr-block `
  --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=$AppName},{Key=Application,Value=$AppName}]" `
  --query Vpc.VpcId --output text @AwsCommon

aws ec2 wait vpc-available --vpc-ids $VpcId @AwsCommon
```

Uma VPC não padrão precisa de resolução e hostnames DNS habilitados para o DNS
privado do VPC Endpoint funcionar:

```powershell
aws ec2 modify-vpc-attribute `
  --vpc-id $VpcId --enable-dns-support Value=true @AwsCommon
aws ec2 modify-vpc-attribute `
  --vpc-id $VpcId --enable-dns-hostnames Value=true @AwsCommon
```

A associação do bloco IPv6 é assíncrona. Consulte até o estado ser
`associated`, extraia o `/56` da VPC e derive o primeiro `/64` para a subnet:

```powershell
$VpcIpv6Cidr = $null
for ($attempt = 1; $attempt -le 30; $attempt++) {
  $VpcIpv6Cidr = aws ec2 describe-vpcs `
    --vpc-ids $VpcId `
    --query "Vpcs[0].Ipv6CidrBlockAssociationSet[?Ipv6CidrBlockState.State=='associated'].Ipv6CidrBlock | [0]" `
    --output text @AwsCommon

  if (-not [string]::IsNullOrWhiteSpace($VpcIpv6Cidr) -and $VpcIpv6Cidr -ne "None") { break }
  Start-Sleep -Seconds 2
}

$SubnetIpv6Cidr = "$($VpcIpv6Cidr.Split('/')[0])/64"
```

## 4. Criar o Internet Gateway, a subnet e as rotas

Crie e anexe o Internet Gateway:

```powershell
$InternetGatewayId = aws ec2 create-internet-gateway `
  --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=$AppName},{Key=Application,Value=$AppName}]" `
  --query InternetGateway.InternetGatewayId --output text @AwsCommon

aws ec2 attach-internet-gateway `
  --internet-gateway-id $InternetGatewayId --vpc-id $VpcId @AwsCommon
```

Consulte uma zona de disponibilidade e crie a subnet dual-stack. A atribuição
automática de IPv6 será habilitada, enquanto a atribuição automática de IPv4
público permanecerá desabilitada:

```powershell
$AvailabilityZone = aws ec2 describe-availability-zones `
  --filters "Name=state,Values=available" `
  --query "AvailabilityZones[0].ZoneName" --output text @AwsCommon

$SubnetId = aws ec2 create-subnet `
  --vpc-id $VpcId `
  --cidr-block $SubnetIpv4Cidr `
  --ipv6-cidr-block $SubnetIpv6Cidr `
  --availability-zone $AvailabilityZone `
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$AppName},{Key=Application,Value=$AppName}]" `
  --query Subnet.SubnetId --output text @AwsCommon

aws ec2 modify-subnet-attribute `
  --subnet-id $SubnetId --assign-ipv6-address-on-creation @AwsCommon
aws ec2 modify-subnet-attribute `
  --subnet-id $SubnetId --no-map-public-ip-on-launch @AwsCommon
```

Crie a tabela de rotas, adicione a rota IPv6 pública e associe-a à subnet:

```powershell
$RouteTableId = aws ec2 create-route-table `
  --vpc-id $VpcId `
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$AppName},{Key=Application,Value=$AppName}]" `
  --query RouteTable.RouteTableId --output text @AwsCommon

aws ec2 create-route `
  --route-table-id $RouteTableId `
  --destination-ipv6-cidr-block ::/0 `
  --gateway-id $InternetGatewayId @AwsCommon

$RouteAssociationId = aws ec2 associate-route-table `
  --route-table-id $RouteTableId `
  --subnet-id $SubnetId `
  --query AssociationId --output text @AwsCommon
```

Não é criada uma rota IPv4 pública: a EC2 do `loto-bot` não precisa de IPv4
público. A rota local da VPC continua permitindo a comunicação privada IPv4
entre `loto-bot`, `whatsapp-notify` e os endpoints de interface.

### 4.1. Criar o endpoint privado do CloudFormation

As instâncias não possuem saída IPv4 para a internet, e o endpoint público
padrão do CloudFormation não oferece o mesmo endpoint S3 dual-stack usado nos
downloads. Crie um único Interface VPC Endpoint compartilhado antes de implantar
qualquer stack EC2 que use `CreationPolicy` e `cfn-signal`:

```powershell
$CloudFormationEndpointSecurityGroupName = "$AppName-cloudformation-endpoint"
$CloudFormationEndpointSecurityGroupId = aws ec2 create-security-group `
  --group-name $CloudFormationEndpointSecurityGroupName `
  --description "Private CloudFormation endpoint for LotoBot EC2 stacks" `
  --vpc-id $VpcId `
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=$CloudFormationEndpointSecurityGroupName},{Key=Application,Value=$AppName}]" `
  --query GroupId --output text @AwsCommon

aws ec2 authorize-security-group-ingress `
  --group-id $CloudFormationEndpointSecurityGroupId `
  --ip-permissions "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=$VpcIpv4Cidr,Description='HTTPS from the shared VPC'}]" `
  @AwsCommon

$CloudFormationVpcEndpointId = aws ec2 create-vpc-endpoint `
  --vpc-id $VpcId `
  --vpc-endpoint-type Interface `
  --service-name "com.amazonaws.$AwsRegion.cloudformation" `
  --subnet-ids $SubnetId `
  --security-group-ids $CloudFormationEndpointSecurityGroupId `
  --private-dns-enabled `
  --tag-specifications "ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=$CloudFormationEndpointSecurityGroupName},{Key=Application,Value=$AppName}]" `
  --query VpcEndpoint.VpcEndpointId --output text @AwsCommon

do {
    $VpcEndpointState = aws ec2 describe-vpc-endpoints `
        --vpc-endpoint-ids $CloudFormationVpcEndpointId `
        --query "VpcEndpoints[0].State" `
        --output text `
        @AwsCommon

    if ($LASTEXITCODE -ne 0) {
        throw "Erro ao consultar o VPC Endpoint '$CloudFormationVpcEndpointId'."
    }

    Write-Host "Estado do VPC Endpoint: $VpcEndpointState"

    if ($VpcEndpointState -eq "failed") {
        throw "Falha na criação do VPC Endpoint '$CloudFormationVpcEndpointId'."
    }

    if ($VpcEndpointState -ne "available") {
        Start-Sleep -Seconds 5
    }

} while ($VpcEndpointState -ne "available")

aws ec2 describe-vpc-endpoints `
  --vpc-endpoint-ids $CloudFormationVpcEndpointId `
  --query "VpcEndpoints[0].{State:State,PrivateDns:PrivateDnsEnabled,Service:ServiceName,SubnetIds:SubnetIds}" `
  --output table @AwsCommon
```

O resultado deve mostrar `State=available` e `PrivateDns=True`. O Security Group
aceita apenas TCP/443 originado do CIDR IPv4 privado da VPC; não abra essa regra
para `0.0.0.0/0`. Como Interface VPC Endpoints têm cobrança contínua por zona de
disponibilidade e por dados, mantenha apenas este endpoint compartilhado para o
CloudFormation na VPC.

## 5. Criar o Key Pair e preparar o template para IPv6

Crie o Key Pair que será associado à EC2 permanente e proteja o arquivo local:

```powershell
aws ec2 create-key-pair `
  --key-name $KeyName `
  --key-type ed25519 `
  --key-format pem `
  --tag-specifications "ResourceType=key-pair,Tags=[{Key=Name,Value=$KeyName},{Key=Application,Value=$StackName}]" `
  --query KeyMaterial --output text @AwsCommon |
  Out-File -FilePath $KeyFile -Encoding ascii

icacls.exe $KeyFile /inheritance:r | Out-Null
icacls.exe $KeyFile /grant:r "$($env:USERNAME):(R)" | Out-Null
```

O `template.yaml` inclui os parâmetros e propriedades necessários para esse
fluxo:

1. receber `KeyName` e `AllowedSshIpv6Cidr` como parâmetros;
2. definir `KeyName: !Ref KeyName` e `Ipv6AddressCount: 1` em
   `ApplicationInstance`;
3. adicionar TCP/22 com `CidrIpv6: !Ref AllowedSshIpv6Cidr` no
   `ApplicationSecurityGroup`;
4. adicionar regras de saída IPv6 para HTTP, HTTPS e DNS usando
   `CidrIpv6: ::/0`, pois as regras atuais usam somente `CidrIp`;
5. gravar `BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080` em
   `/etc/loto-bot.env`.

Os trechos principais implementados são:

```yaml
Parameters:
  KeyName:
    Type: AWS::EC2::KeyPair::KeyName
  AllowedSshIpv6Cidr:
    Type: String

Resources:
  ApplicationSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      SecurityGroupIngress:
        - Description: SSH IPv6 from the local proxy host
          IpProtocol: tcp
          FromPort: 22
          ToPort: 22
          CidrIpv6: !Ref AllowedSshIpv6Cidr
      SecurityGroupEgress:
        - Description: HTTPS over IPv6
          IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIpv6: ::/0

  ApplicationInstance:
    Type: AWS::EC2::Instance
    Properties:
      KeyName: !Ref KeyName
      Ipv6AddressCount: 1
```

Essas propriedades já estão mescladas aos recursos existentes. Não crie uma
segunda definição com os mesmos nomes lógicos ao personalizar o template.

Depois de atualizar o template, valide-o antes do deploy:

```powershell
sam validate --lint --template-file template.yaml
```

## 6. Criar o Security Group de integração

Crie o grupo na nova VPC e fora das stacks de aplicação para que nenhuma delas
dependa da outra. Ele não precisa de regras de entrada: será anexado ao
`loto-bot` como identidade de origem e referenciado pelo `whatsapp-notify` em
sua regra de entrada.

```powershell
$SecurityGroupId = aws ec2 create-security-group `
  --group-name $AppName `
  --description "Shared source identity for $AppName internal integrations" `
  --vpc-id $VpcId `
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=$AppName},{Key=Purpose,Value=internal-integration}]" `
  --query GroupId --output text `
  --region $AwsRegion --profile $AwsProfile
```

Não adicione regras de entrada. O `template.yaml` anexa esse grupo à EC2 do
`loto-bot` por meio do parâmetro `IntegrationSecurityGroupId`. Caso ele já
exista, recupere-o pela nova VPC e pelo nome:

```powershell
$SecurityGroupId = aws ec2 describe-security-groups `
  --filters "Name=vpc-id,Values=$VpcId" "Name=group-name,Values=$AppName" `
  --query "SecurityGroups[0].GroupId" --output text `
  --region $AwsRegion --profile $AwsProfile
```

Guarde o ID para os dois deploys. Não abra portas públicas nesse grupo e não o remova enquanto qualquer uma das stacks o estiver usando.

Confirme que o grupo pertence à VPC criada no passo 3:

```powershell
aws ec2 describe-security-groups `
  --group-ids $SecurityGroupId `
  --query "SecurityGroups[0].{GroupId:GroupId,VpcId:VpcId}" `
  --output table @AwsCommon
```

## 7. Segredo da aplicação

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
  --name $OAuthSecretName `
  --secret-string $ApplicationSecretPath `
  --query ARN --output text `
  --region $AwsRegion --profile $AwsProfile
```

Se o segredo já existir, obtenha seu ARN em vez de criá-lo novamente.

## 8. Implantar as Lambdas na VPC compartilhada e obter os ARNs

As duas Lambdas dependem de `$VpcId` e `$SubnetId`; portanto, elas devem ser
implantadas somente depois das etapas 3 e 4. Cada stack cria seu próprio
Security Group de saída na VPC compartilhada e habilita IPv6 na configuração
da função. A subnet precisa continuar dual-stack e com rota `::/0`.

No projeto `mail-sender-aws`:

```powershell
sam validate --lint --template-file template.yaml
sam deploy `
  --template-file template.yaml `
  --stack-name mail-sender `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --region $AwsRegion `
  --profile $AwsProfile `
  --parameter-overrides `
    VpcId=$VpcId SubnetId=$SubnetId `
    SesFrom="<remetente-verificado>"
```

No projeto `gmail-reader-aws`, depois de criar ou recuperar o segredo OAuth:

```powershell
$GmailOAuthSecretArn = "<arn-do-segredo-oauth-do-gmail>"

sam validate --lint --template-file template.yaml
sam deploy `
  --template-file template.yaml `
  --stack-name gmail-reader `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --region $AwsRegion `
  --profile $AwsProfile `
  --parameter-overrides `
    VpcId=$VpcId SubnetId=$SubnetId `
    GmailOAuthSecretArn=$GmailOAuthSecretArn `
    WaitTimeoutSeconds=15
```

O VPC Endpoint de Lambda criado pela stack do `loto-bot` continua necessário:
ele fornece o endpoint privado usado pela EC2 para chamar a API `Invoke`. A
associação das funções à VPC controla a conectividade de saída executada pelo
código das Lambdas e não substitui esse endpoint de serviço.

Depois dos dois deploys, obtenha os ARNs:

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

Esses valores são ARNs de função, não URLs. O bootstrap grava `INTEGRATION_MODE=AWS`, `AWS_DEFAULT_REGION` com a região da stack, `GMAIL_READER_FUNCTION_NAME` e `MAIL_SENDER_FUNCTION_NAME`. O `boto3` usa `AWS_DEFAULT_REGION` para invocar as funções Lambda. As variáveis `GMAIL_READER_URL` e `MAIL_SENDER_URL` são ignoradas nesse modo.

O bootstrap também grava `BROWSER_TIMEOUT_SECONDS=20` para dar ao Chromium tempo
de concluir a navegação pelo túnel SOCKS5. A seleção de modalidade só é
considerada concluída após o clique e o redirecionamento para a página da
modalidade. Uma instância já inicializada não reaplica o User Data quando o
template muda; para receber também a correção da automação, publique um novo
ZIP com `src/` atualizado e substitua a instância de forma controlada. Isso
perde o perfil do navegador no volume raiz e exigirá nova autenticação.

## 9. Publicar o artefato

O ZIP deve conter `pyproject.toml`, `src/` e os demais arquivos versionados na raiz. O `pyproject.toml` deve declarar `boto3`, usado para invocar as funções Lambda de Gmail Reader e Mail Sender em `INTEGRATION_MODE=AWS`. `git archive` evita incluir `.venv`, perfis do navegador e segredos locais.

```powershell
aws s3api create-bucket --bucket $ArtifactBucket --region $AwsRegion --profile $AwsProfile
aws s3api put-public-access-block --bucket $ArtifactBucket --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" --region $AwsRegion --profile $AwsProfile
aws s3api put-bucket-encryption --bucket $ArtifactBucket --server-side-encryption-configuration 'Rules=[{ApplyServerSideEncryptionByDefault={SSEAlgorithm=AES256}}]' --region $AwsRegion --profile $AwsProfile

$ArtifactVersion = Get-Date -Format "yyyyMMdd-HHmmss"
$ArtifactKey = "$StackName/releases/$ArtifactVersion/$StackName.zip"
$ArtifactFile = Join-Path $env:TEMP "$StackName-$ArtifactVersion.zip"

tar -a -c -f $ArtifactFile pyproject.toml README.md src
tar -tf $ArtifactFile | Sort-Object

$ArtifactSha256 = (Get-FileHash -Algorithm SHA256 $ArtifactFile).Hash.ToLower()

aws s3 cp $ArtifactFile "s3://$ArtifactBucket/$ArtifactKey" --sse AES256 --metadata "sha256=$ArtifactSha256" --region $AwsRegion --profile $AwsProfile
aws s3api head-object --bucket $ArtifactBucket --key $ArtifactKey --region $AwsRegion --profile $AwsProfile
```

## 10. Implantar o `whatsapp-notify`

Siga o guia do projeto `whatsapp-notify`, usando `$VpcId`, `$SubnetId` e `IntegrationSecurityGroupId=$SecurityGroupId`. Esse deploy não depende da existência da stack do `loto-bot`, mas deve usar exatamente a mesma rede criada nas etapas 3 e 4.

```powershell
$WhatsAppNotifyUrl = aws cloudformation describe-stacks `
  --stack-name whatsapp-notify `
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]" `
  --output text --region $AwsRegion --profile $AwsProfile
```

O valor deve começar com `http://` e apontar para o DNS privado da EC2.

## 11. Implantar o `loto-bot`

```powershell
sam validate --lint --template-file template.yaml
sam build --template-file template.yaml
sam deploy `
  --template-file template.yaml `
  --stack-name $StackName `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --region $AwsRegion `
  --profile $AwsProfile `
  --parameter-overrides `
    VpcId=$VpcId SubnetId=$SubnetId AmiId=$AmiId `
    InstanceType=$InstanceType AllowedCidr=0.0.0.0/32 `
    KeyName=$KeyName AllowedSshIpv6Cidr=$AllowedSshIpv6Cidr `
    ArtifactBucket=$ArtifactBucket ArtifactKey=$ArtifactKey ArtifactSha256=$ArtifactSha256 `
    ApplicationSecretArn=$ApplicationSecretArn `
    GmailReaderFunctionArn=$GmailReaderFunctionArn `
    MailSenderFunctionArn=$MailSenderFunctionArn `
    WhatsAppNotifyUrl=$WhatsAppNotifyUrl `
    IntegrationSecurityGroupId=$SecurityGroupId `
    ConfirmPayment=false MongoDbEnabled=false RootVolumeSize=20
```

Mantenha `ConfirmPayment=false` até concluir os testes controlados. `AllowedCidr=0.0.0.0/32` mantém o acesso externo fechado e usa somente SSM. O template anexa à EC2 tanto seu Security Group de aplicação quanto o grupo externo de integração.

## 12. Validação operacional

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

O serviço inicia pelo comando `loto-bot`, que aplica `LOG_LEVEL` e o formato de
log da aplicação. O bootstrap mantém `LOG_LEVEL=INFO`; para diagnosticar uma
falha, defina temporariamente `LOG_LEVEL=DEBUG` em `/etc/loto-bot.env`, reinicie
o serviço e acompanhe com `sudo journalctl -u loto-bot -f --full -o short-iso-precise`.
Depois volte a `INFO`. O reinício interrompe a sessão
em andamento, e logs DEBUG podem conter dados da sessão e das apostas; revise
e oculte informações sensíveis antes de compartilhá-los.

Para acesso local, execute o output `PortForwardCommand` e use `http://127.0.0.1:8080`. Nenhum cabeçalho de chave de API é necessário nas chamadas internas.

Confirme que a role limita `lambda:InvokeFunction` aos dois ARNs, `secretsmanager:GetSecretValue` ao segredo da aplicação e `s3:GetObject` a `loto-bot/releases/*`.

## 13. Atualizações e rollback

Para uma nova versão, execute os testes, gere outro ZIP e SHA-256, envie-o para uma chave S3 versionada, faça deploy e revise o change set. O código e o ambiente são instalados pelo User Data; uma simples alteração de parâmetro não reexecuta o script em uma EC2 existente. Durante o bootstrap, `AWS_USE_DUALSTACK_ENDPOINT=true` permite que AWS CLI, S3 e Secrets Manager usem IPv6. O `cfn-signal` usa o hostname regional padrão do CloudFormation, resolvido para IPv4 privado pelo Interface VPC Endpoint compartilhado. A variável dual-stack não é persistida em `/etc/loto-bot.env`, preservando o DNS privado dos endpoints de interface em runtime.

Para rollback, reaplique o `ArtifactKey` e o `ArtifactSha256` anteriores e substitua a instância de forma controlada. O perfil do navegador está no volume raiz e será perdido se a instância for substituída; planeje nova autenticação.

Uma EC2 já criada não reinstala dependências quando `pyproject.toml` ou o ZIP
mudam. Para recuperar a instância atual após o erro `No module named 'boto3'`,
instale a dependência na virtualenv da aplicação e reinicie o serviço:

```bash
sudo -u loto-bot /opt/loto-bot/app/.venv/bin/python -m pip install 'boto3>=1.35.3'
sudo systemctl restart loto-bot
sudo -u loto-bot /opt/loto-bot/app/.venv/bin/python -c 'import boto3; print(boto3.__version__)'
```

Essa recuperação local não substitui a publicação de um artefato novo contendo
o `pyproject.toml` corrigido; futuras instâncias instalam as dependências a
partir desse artefato.

Se a instância existente registrar `You must specify a region` ao iniciar uma
sessão, configure a região para o processo `loto-bot` e reinicie o serviço.
Substitua `us-east-1` pela região em que a stack foi implantada, se diferente:

```bash
if ! sudo grep -q '^AWS_DEFAULT_REGION=' /etc/loto-bot.env; then
  echo 'AWS_DEFAULT_REGION=us-east-1' | sudo tee -a /etc/loto-bot.env >/dev/null
fi
sudo systemctl restart loto-bot
sudo grep '^AWS_DEFAULT_REGION=' /etc/loto-bot.env
sudo journalctl -u loto-bot -n 50 --no-pager
```

O `sam deploy` que apenas atualiza o User Data não reaplica essa configuração
à EC2 já inicializada. O template corrigido passa a gravá-la em instâncias
criadas posteriormente.

Se a EC2 atual ainda iniciar o Uvicorn diretamente, `LOG_LEVEL=DEBUG` não ativa
o formato detalhado da aplicação. Após encerrar qualquer sessão em andamento,
crie um override do systemd com `sudo systemctl edit loto-bot`:

```ini
[Service]
ExecStart=
ExecStart=/opt/loto-bot/app/.venv/bin/loto-bot
```

Salve o override e confirme a inicialização e o comando efetivo:

```bash
sudo systemctl daemon-reload
sudo systemctl restart loto-bot
sudo systemctl cat loto-bot
sudo journalctl -u loto-bot -n 100 --no-pager --full -o short-iso-precise
```

Esse override vale apenas para a EC2 atual. Instâncias novas recebem o comando
diretamente do template atualizado.

## 14. Custos

- confira EC2, EBS, transferência, S3, Secrets Manager e CloudWatch Logs;
- monitore créditos de CPU das instâncias T;
- os VPC Endpoints de interface para Lambda e CloudFormation geram cobrança contínua;
- `t3.small` e volumes acima da franquia podem gerar custo;
- configure AWS Budgets e alertas antes do deploy.

## 15. Validar o IPv6 e o proxy local

No Windows, valide a conectividade IPv6 antes de iniciar o teste:

```powershell
ping -6 google.com

curl.exe -6 https://api64.ipify.org
```

O segundo comando deve retornar um endereço IPv6 público, por exemplo:

```text
2804:xxxx:xxxx:xxxx::1234
```

Se o `ping` ou o `curl.exe` falhar, corrija a conectividade IPv6 local antes de
executar o script da EC2.

Em seguida, confirme que o proxy SOCKS5 local está escutando:

```powershell
Test-NetConnection 127.0.0.1 -Port 1080
```

## 16. Validar o Chromium remoto pela EC2 descartável

Use os scripts de referência para testar a VPC IPv6, a EC2 sem IPv4 público, a rota `::/0`, o Security Group restrito ao IPv6 `/128`, o túnel reverso e `test_browser_proxy.py`:

```powershell
cd $YourDir\loto-bot\scripts
Unblock-File -LiteralPath .\start-browser-socks5-ipv6-aws.ps1
Unblock-File -LiteralPath .\stop-socks5-ipv6-aws.ps1

.\start-browser-socks5-ipv6-aws.ps1 `
  -AwsProfile $AwsProfile `
  -AwsRegion $AwsRegion `
  -InstanceType "$InstanceType" `
  -StateFile ".\browser-socks5-ipv6-aws-state.json"
```

O resultado deve conter `Teste CAIXA via Chromium: OK` e `Falha sem fallback confirmada`. Limpe sempre os recursos, inclusive após falhas:

```powershell
.\stop-socks5-ipv6-aws.ps1 -StateFile ".\browser-socks5-ipv6-aws-state.json"
```

## 17. Manter o túnel SOCKS5 na instância permanente

Após o deploy, consulte o IPv6 atribuído pela stack:

```powershell
$InstanceIpv6 = aws ec2 describe-instances `
  --instance-ids $InstanceId `
  --query "Reservations[0].Instances[0].NetworkInterfaces[0].Ipv6Addresses[0].Ipv6Address" `
  --output text @AwsCommon

if ([string]::IsNullOrWhiteSpace($InstanceIpv6) -or $InstanceIpv6 -eq "None") {
  throw "A instância não recebeu um IPv6."
}
```

Defina as opções SSH e aguarde até que o serviço esteja realmente aceitando
conexões. O estado `instance-status-ok` não garante que o `sshd` já terminou de
inicializar:

```powershell
$SshReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
  Write-Host "Testando SSH ($attempt/30): $RemoteUser@$InstanceIpv6"
  $PreviousErrorActionPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    & ssh @SshOptions "$RemoteUser@$InstanceIpv6" "true" 2>&1 | Out-Null
    $SshExitCode = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
  }

  if ($SshExitCode -eq 0) {
    $SshReady = $true
    Write-Host "SSH disponível."
    break
  }

  Write-Host "SSH ainda não disponível. Exit code: $SshExitCode"
  Start-Sleep -Seconds 10
}

if (-not $SshReady) {
  throw "A instância ficou saudável, mas o SSH via IPv6 não respondeu."
}
```

Inicie o túnel SSH reverso em segundo plano e confirme que o processo continua
ativo após a negociação inicial:

```powershell
$TunnelArguments = @(
  "-6",
  "-i", $KeyFile,
  "-N", "-T",
  "-o", "ExitOnForwardFailure=yes",
  "-o", "ServerAliveInterval=30",
  "-o", "ServerAliveCountMax=3",
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "UserKnownHostsFile=$KnownHostsFile",
  "-R", "127.0.0.1:1080",
  "$RemoteUser@$InstanceIpv6"
)

$TunnelProcess = Start-Process ssh `
  -ArgumentList $TunnelArguments `
  -WindowStyle Hidden `
  -PassThru
$TunnelProcessId = $TunnelProcess.Id

Start-Sleep -Seconds 5
if ($TunnelProcess.HasExited) {
  throw "O processo do túnel SSH terminou antes da validação."
}

Write-Host "Túnel SOCKS5 iniciado. PID: $TunnelProcessId"
```

O Security Group deve permitir TCP/22 somente para o IPv6 `/128` local. Não
exponha a porta 1080 na interface da EC2. Se o IPv6 local mudar, atualize a
regra. Ao encerrar o túnel, o Chromium deve falhar sem fallback direto.

Para encerrar o túnel de forma controlada:

```powershell
Stop-Process -Id $TunnelProcessId
Wait-Process -Id $TunnelProcessId -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $KnownHostsFile -Force -ErrorAction SilentlyContinue
```

## 18. Validação específica do proxy

Com o túnel ativo, use SSM e confira o serviço e o listener:

```powershell
aws ssm start-session --target $InstanceId --region $AwsRegion --profile $AwsProfile
```

```bash
sudo systemctl status loto-bot --no-pager
sudo journalctl -u loto-bot -n 100 --no-pager
curl -fsS http://127.0.0.1:8000/health
ss -lnt | grep '127.0.0.1:1080'
```

Execute um fluxo controlado com `ConfirmPayment=false`, valide a CAIXA, encerre o túnel e confirme a falha sem fallback.

## 19. Custos adicionais e checklist do proxy

Monitore transferência, EBS, CloudWatch e o VPC Endpoint de interface para Lambda. Configure AWS Budgets e remova imediatamente os recursos descartáveis.

- [ ] IPv6 local validado.
- [ ] Proxy local em `127.0.0.1:1080`.
- [ ] Teste IPv6 descartável aprovado e limpo.
- [ ] EC2 permanente sem IPv4 público.
- [ ] `BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080` configurado.
- [ ] `BROWSER_TIMEOUT_SECONDS=20` configurado para o Chromium na EC2.
- [ ] Túnel reverso supervisionado.
- [ ] Falha sem fallback confirmada.

## 20. Checklist

- [ ] Outputs `FunctionArn` das duas Lambdas obtidos.
- [ ] Stacks `mail-sender-aws` e `gmail-reader-aws` implantadas com o mesmo `VpcId` e `SubnetId` do `loto-bot`.
- [ ] VPC criada com bloco IPv4 e bloco IPv6 fornecido pela AWS.
- [ ] DNS support e DNS hostnames habilitados na VPC.
- [ ] Internet Gateway criado e anexado à VPC.
- [ ] Subnet dual-stack criada sem atribuição automática de IPv4 público.
- [ ] Rota `::/0` criada e tabela de rotas associada à subnet.
- [ ] Key Pair criado e arquivo PEM protegido localmente.
- [ ] Template atualizado com `KeyName`, IPv6, SSH IPv6 e egress IPv6.
- [ ] `INTEGRATION_MODE=AWS` no ambiente implantado.
- [ ] `AWS_DEFAULT_REGION` no ambiente do serviço corresponde à região da stack.
- [ ] Artefato versionado no S3 e SHA-256 conferido.
- [ ] Segredo contém somente as cinco chaves esperadas.
- [ ] `ConfirmPayment=false` no primeiro deploy.
- [ ] Role limitada aos recursos necessários.
- [ ] VPC Endpoint Lambda com DNS privado habilitado.
- [ ] VPC Endpoint CloudFormation compartilhado disponível e com DNS privado habilitado antes dos deploys EC2.
- [ ] Security Group de integração criado fora das stacks e informado nos dois deploys.
- [ ] WhatsApp aceita porta 80 somente do Security Group de integração.
- [ ] `WHATSAPP_NOTIFY_URL` usa DNS privado e HTTP.
- [ ] Nenhuma variável ou chamada usa chave de API compartilhada.
- [ ] Serviços validados via SSM.
- [ ] Orçamento e alertas configurados.
