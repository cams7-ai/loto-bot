# Migração do `loto-bot` para AWS a partir do Linux

Versão Bash/Linux do [guia de migração](AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md). A arquitetura, os parâmetros do [`template.yaml`](../template.yaml), os cuidados de custo e os testes funcionais são os mesmos. Execute os blocos no **mesmo terminal Bash**, a partir da raiz deste repositório, substituindo os valores entre `<...>`. Os scripts `.sh` usam Python 3.12+ e AWS CLI; não exigem PowerShell.

> A arquitetura usa VPC Endpoints de interface, com cobrança contínua. Consulte os preços da região e configure um orçamento antes de criar recursos. Os testes descartáveis criam EC2, EBS, VPC e outros recursos cobrados; execute o script `stop` mesmo se o teste falhar.

## 1. Pré-requisitos e variáveis

Instale AWS CLI, SAM CLI, Python 3.12+, OpenSSH (`ssh` e `scp`), `curl`, `zip` e Git. Configure um perfil AWS com acesso a CloudFormation, EC2, IAM, S3, SSM, Secrets Manager, DynamoDB e VPC Endpoints. O computador local precisa de IPv6 público para o fluxo principal.

```bash
AWS_PROFILE_NAME='<perfil>'
AWS_REGION='us-east-1'
AWS_ARGS=(--region "$AWS_REGION" --profile "$AWS_PROFILE_NAME")
APP_NAME='loto-bot'
STACK_NAME="$APP_NAME"
REMOTE_USER='ubuntu'
INSTANCE_TYPE='t3.micro'
DYNAMODB_TABLE_NAME='loto-bot-bets'
KEY_NAME="$STACK_NAME"
KEY_FILE="$HOME/.ssh/$KEY_NAME.pem"
KNOWN_HOSTS_FILE="$HOME/.ssh/$KEY_NAME-known-hosts"
OAUTH_SECRET_NAME="$STACK_NAME/application"
APPLICATION_SECRET_PATH='file://application-secret.json'
LOCAL_PUBLIC_IPV6="$(curl -6 -fsS https://api64.ipify.org)"
ALLOWED_SSH_IPV6_CIDR="$LOCAL_PUBLIC_IPV6/128"
AMI_ID="$(aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text "${AWS_ARGS[@]}")"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --profile "$AWS_PROFILE_NAME")"
ARTIFACT_BUCKET="$STACK_NAME-artifacts-$ACCOUNT_ID-$AWS_REGION"
aws sts get-caller-identity "${AWS_ARGS[@]}"
```

Confirme `curl -6 -fsS https://api64.ipify.org` e `getent ahosts api.ipify.org` no Linux local. O `ssh -R 127.0.0.1:1080` cria o listener SOCKS5 **na EC2**; não é necessário iniciar um servidor na porta 1080 do computador Linux. O cliente SSH local resolve os nomes de destino e abre as conexões de saída, portanto o DNS local deve funcionar para `api.ipify.org` e `www.loteriasonline.caixa.gov.br`. `INTEGRATION_MODE=AWS` usa DynamoDB e chama as Lambdas pelo SDK; o acesso ao WhatsApp é HTTP privado.

## 2. VPC dual-stack, subnet e rotas

```bash
VPC_IPV4_CIDR='10.77.0.0/16'
SUBNET_IPV4_CIDR='10.77.1.0/24'
VPC_ID="$(aws ec2 create-vpc --cidr-block "$VPC_IPV4_CIDR" --amazon-provided-ipv6-cidr-block --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=$APP_NAME},{Key=Application,Value=$APP_NAME}]" --query Vpc.VpcId --output text "${AWS_ARGS[@]}")"
aws ec2 wait vpc-available --vpc-ids "$VPC_ID" "${AWS_ARGS[@]}"
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support Value=true "${AWS_ARGS[@]}"
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames Value=true "${AWS_ARGS[@]}"

VPC_IPV6_CIDR=''
for attempt in {1..30}; do
  VPC_IPV6_CIDR="$(aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --query "Vpcs[0].Ipv6CidrBlockAssociationSet[?Ipv6CidrBlockState.State=='associated'].Ipv6CidrBlock | [0]" --output text "${AWS_ARGS[@]}")"
  [[ "$VPC_IPV6_CIDR" != 'None' && -n "$VPC_IPV6_CIDR" ]] && break
  sleep 2
done
[[ "$VPC_IPV6_CIDR" != 'None' && -n "$VPC_IPV6_CIDR" ]] || { echo 'IPv6 da VPC indisponível' >&2; return 1 2>/dev/null || exit 1; }
SUBNET_IPV6_CIDR="$(python3 -c 'import ipaddress,sys; print(next(ipaddress.ip_network(sys.argv[1]).subnets(new_prefix=64)))' "$VPC_IPV6_CIDR")"

INTERNET_GATEWAY_ID="$(aws ec2 create-internet-gateway --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=$APP_NAME}]" --query InternetGateway.InternetGatewayId --output text "${AWS_ARGS[@]}")"
aws ec2 attach-internet-gateway --internet-gateway-id "$INTERNET_GATEWAY_ID" --vpc-id "$VPC_ID" "${AWS_ARGS[@]}"
AVAILABILITY_ZONE="$(aws ec2 describe-availability-zones --filters Name=state,Values=available --query 'AvailabilityZones[0].ZoneName' --output text "${AWS_ARGS[@]}")"
SUBNET_ID="$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block "$SUBNET_IPV4_CIDR" --ipv6-cidr-block "$SUBNET_IPV6_CIDR" --availability-zone "$AVAILABILITY_ZONE" --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$APP_NAME}]" --query Subnet.SubnetId --output text "${AWS_ARGS[@]}")"
aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_ID" --assign-ipv6-address-on-creation "${AWS_ARGS[@]}"
aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_ID" --no-map-public-ip-on-launch "${AWS_ARGS[@]}"
ROUTE_TABLE_ID="$(aws ec2 create-route-table --vpc-id "$VPC_ID" --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$APP_NAME}]" --query RouteTable.RouteTableId --output text "${AWS_ARGS[@]}")"
aws ec2 create-route --route-table-id "$ROUTE_TABLE_ID" --destination-ipv6-cidr-block ::/0 --gateway-id "$INTERNET_GATEWAY_ID" "${AWS_ARGS[@]}"
ROUTE_ASSOCIATION_ID="$(aws ec2 associate-route-table --route-table-id "$ROUTE_TABLE_ID" --subnet-id "$SUBNET_ID" --query AssociationId --output text "${AWS_ARGS[@]}")"
```

A rota local IPv4 da VPC permite a comunicação privada entre aplicações. Não crie rota IPv4 pública para a EC2 do `loto-bot`.

## 3. Endpoint CloudFormation e identidade de integração

O endpoint CloudFormation compartilhado é necessário para `cfn-signal` das stacks EC2. Mantenha DNS privado habilitado e entrada TCP/443 restrita ao CIDR IPv4 da VPC.

```bash
CFN_GROUP_NAME="$APP_NAME-cloudformation-endpoint"
CFN_GROUP_ID="$(aws ec2 create-security-group --group-name "$CFN_GROUP_NAME" --description 'Private CloudFormation endpoint for LotoBot EC2 stacks' --vpc-id "$VPC_ID" --query GroupId --output text "${AWS_ARGS[@]}")"
aws ec2 authorize-security-group-ingress --group-id "$CFN_GROUP_ID" --ip-permissions "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=$VPC_IPV4_CIDR}]" "${AWS_ARGS[@]}"
CFN_ENDPOINT_ID="$(aws ec2 create-vpc-endpoint --vpc-id "$VPC_ID" --vpc-endpoint-type Interface --service-name "com.amazonaws.$AWS_REGION.cloudformation" --subnet-ids "$SUBNET_ID" --security-group-ids "$CFN_GROUP_ID" --private-dns-enabled --query VpcEndpoint.VpcEndpointId --output text "${AWS_ARGS[@]}")"
for attempt in {1..60}; do
  endpoint_state="$(aws ec2 describe-vpc-endpoints --vpc-endpoint-ids "$CFN_ENDPOINT_ID" --query 'VpcEndpoints[0].State' --output text "${AWS_ARGS[@]}")"
  [[ "$endpoint_state" == 'available' ]] && break
  [[ "$endpoint_state" == 'failed' ]] && { echo 'Endpoint CloudFormation falhou' >&2; return 1 2>/dev/null || exit 1; }
  sleep 5
done
[[ "$endpoint_state" == 'available' ]] || { echo 'Endpoint CloudFormation indisponível' >&2; return 1 2>/dev/null || exit 1; }
./scripts/test-shared-cloudformation-endpoint.sh --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" --vpc-id "$VPC_ID"

INTEGRATION_GROUP_ID="$(aws ec2 create-security-group --group-name "$APP_NAME" --description 'Shared source identity for LotoBot internal integrations' --vpc-id "$VPC_ID" --query GroupId --output text "${AWS_ARGS[@]}")"
```

Não abra entrada no grupo de integração. O `whatsapp-notify` deve referenciá-lo na regra de entrada da porta 80.

## 4. Chave SSH e segredo

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
umask 077
aws ec2 create-key-pair --key-name "$KEY_NAME" --key-type ed25519 --key-format pem --query KeyMaterial --output text "${AWS_ARGS[@]}" > "$KEY_FILE"
chmod 600 "$KEY_FILE"
sam validate --lint --template-file template.yaml
```

Crie `application-secret.json` na raiz do projeto, sem versionar:

```json
{
  "bettor_cpf": "<cpf>",
  "bettor_password": "<senha>",
  "credit_card_last_digits": "<ultimos-digitos>",
  "credit_card_security_code": "<codigo-seguranca>",
  "mail_to": "<destinatario>"
}
```

```bash
chmod 600 application-secret.json
APPLICATION_SECRET_ARN="$(aws secretsmanager create-secret --name "$OAUTH_SECRET_NAME" --secret-string "$APPLICATION_SECRET_PATH" --query ARN --output text "${AWS_ARGS[@]}")"
```

Se o segredo já existir, recupere o ARN com `aws secretsmanager describe-secret` em vez de criá-lo novamente.

## 5. Lambdas e WhatsApp na VPC compartilhada

Implante `mail-sender-aws` e `gmail-reader-aws` conforme seus próprios projetos, usando `VpcId=$VPC_ID` e `SubnetId=$SUBNET_ID`. Para `mail-sender-aws`, informe `SesFrom`; para `gmail-reader-aws`, informe `GmailOAuthSecretArn` e `WaitTimeoutSeconds=15`. Execute os comandos no diretório de cada projeto:

```bash
sam validate --lint --template-file template.yaml
sam deploy --template-file template.yaml --stack-name mail-sender --resolve-s3 --capabilities CAPABILITY_IAM --region "$AWS_REGION" --profile "$AWS_PROFILE_NAME" --parameter-overrides "VpcId=$VPC_ID" "SubnetId=$SUBNET_ID" 'SesFrom=<remetente-verificado>'
```

```bash
GMAIL_OAUTH_SECRET_ARN='<arn-do-segredo-oauth-do-gmail>'
sam validate --lint --template-file template.yaml
sam deploy --template-file template.yaml --stack-name gmail-reader --resolve-s3 --capabilities CAPABILITY_IAM --region "$AWS_REGION" --profile "$AWS_PROFILE_NAME" --parameter-overrides "VpcId=$VPC_ID" "SubnetId=$SUBNET_ID" "GmailOAuthSecretArn=$GMAIL_OAUTH_SECRET_ARN" WaitTimeoutSeconds=15
```

De volta à raiz do `loto-bot`:

```bash
GMAIL_READER_FUNCTION_ARN="$(aws cloudformation describe-stacks --stack-name gmail-reader --query "Stacks[0].Outputs[?OutputKey=='FunctionArn'].OutputValue | [0]" --output text "${AWS_ARGS[@]}")"
MAIL_SENDER_FUNCTION_ARN="$(aws cloudformation describe-stacks --stack-name mail-sender --query "Stacks[0].Outputs[?OutputKey=='FunctionArn'].OutputValue | [0]" --output text "${AWS_ARGS[@]}")"
```

Implante `whatsapp-notify` na mesma VPC e subnet, com `IntegrationSecurityGroupId=$INTEGRATION_GROUP_ID`. Obtenha o endereço privado HTTP:

```bash
WHATSAPP_NOTIFY_URL="$(aws cloudformation describe-stacks --stack-name whatsapp-notify --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]" --output text "${AWS_ARGS[@]}")"
```

## 6. Artefato, DynamoDB e deploy

```bash
if [[ "$AWS_REGION" == 'us-east-1' ]]; then
  aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" "${AWS_ARGS[@]}"
else
  aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --create-bucket-configuration "LocationConstraint=$AWS_REGION" "${AWS_ARGS[@]}"
fi
aws s3api put-public-access-block --bucket "$ARTIFACT_BUCKET" --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true' "${AWS_ARGS[@]}"
aws s3api put-bucket-encryption --bucket "$ARTIFACT_BUCKET" --server-side-encryption-configuration 'Rules=[{ApplyServerSideEncryptionByDefault={SSEAlgorithm=AES256}}]' "${AWS_ARGS[@]}"
ARTIFACT_VERSION="$(date -u +%Y%m%d-%H%M%S)"
ARTIFACT_KEY="$STACK_NAME/releases/$ARTIFACT_VERSION/$STACK_NAME.zip"
ARTIFACT_FILE="$(mktemp --suffix=.zip)"
git archive --format=zip --output="$ARTIFACT_FILE" HEAD pyproject.toml README.md src
ARTIFACT_SHA256="$(sha256sum "$ARTIFACT_FILE" | cut -d' ' -f1)"
aws s3 cp "$ARTIFACT_FILE" "s3://$ARTIFACT_BUCKET/$ARTIFACT_KEY" --sse AES256 --metadata "sha256=$ARTIFACT_SHA256" "${AWS_ARGS[@]}"

./scripts/create-dynamodb-aws.sh --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" --table "$DYNAMODB_TABLE_NAME"
./scripts/test-shared-cloudformation-endpoint.sh --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" --vpc-id "$VPC_ID"
sam validate --lint --template-file template.yaml
sam build --template-file template.yaml
sam deploy --template-file template.yaml --stack-name "$STACK_NAME" --resolve-s3 --capabilities CAPABILITY_IAM --region "$AWS_REGION" --profile "$AWS_PROFILE_NAME" --parameter-overrides \
  "VpcId=$VPC_ID" "SubnetId=$SUBNET_ID" "AmiId=$AMI_ID" "InstanceType=$INSTANCE_TYPE" UseLambdaVpcEndpoint=true \
  "KeyName=$KEY_NAME" "AllowedSshIpv6Cidr=$ALLOWED_SSH_IPV6_CIDR" \
  "ArtifactBucket=$ARTIFACT_BUCKET" "ArtifactKey=$ARTIFACT_KEY" "ArtifactSha256=$ARTIFACT_SHA256" \
  "ApplicationSecretArn=$APPLICATION_SECRET_ARN" "GmailReaderFunctionArn=$GMAIL_READER_FUNCTION_ARN" \
  "MailSenderFunctionArn=$MAIL_SENDER_FUNCTION_ARN" "WhatsAppNotifyUrl=$WHATSAPP_NOTIFY_URL" \
  "IntegrationSecurityGroupId=$INTEGRATION_GROUP_ID" ConfirmPayment=false \
  "DynamoDbTableName=$DYNAMODB_TABLE_NAME" RootVolumeSize=20
```

Use `ConfirmPayment=false` até concluir os testes. O User Data não é reaplicado quando apenas `ArtifactKey` muda; para atualizar a aplicação em uma EC2 existente, planeje uma atualização controlada ou substituição da instância. A substituição perde o perfil Chromium do volume raiz.

## 7. Validação e túnel SOCKS5 permanente

```bash
INSTANCE_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue | [0]" --output text "${AWS_ARGS[@]}")"
INSTANCE_IPV6="$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].NetworkInterfaces[0].Ipv6Addresses[0].Ipv6Address' --output text "${AWS_ARGS[@]}")"
SSH_OPTS=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=$KNOWN_HOSTS_FILE" -o ConnectTimeout=15)
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'sudo systemctl status loto-bot --no-pager'
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl -fsS http://127.0.0.1:8000/health'
```

Para acessar a API localmente, deixe o túnel aberto em outro terminal: `ssh "${SSH_OPTS[@]}" -N -T -L 127.0.0.1:8080:127.0.0.1:8000 "$REMOTE_USER@$INSTANCE_IPV6"`. A API ficará em `http://127.0.0.1:8080`.

Para fornecer o SOCKS5 local à EC2, execute em outro terminal e mantenha o processo ativo. **Não acrescente `-6` ao cliente SSH**: o IPv6 literal de `$INSTANCE_IPV6` já determina o transporte até a EC2, enquanto os destinos solicitados pelo SOCKS5 podem ter apenas IPv4 (como `api.ipify.org`).

```bash
ssh "${SSH_OPTS[@]}" -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:1080 "$REMOTE_USER@$INSTANCE_IPV6"
```

Se esse terminal imprimir `connect_to <domínio>: unknown host` e o `curl` remoto retornar `(97) connection to proxy closed`, confira primeiro se a opção `-6` foi removida do comando do túnel. O OpenSSH aplica a família de endereços também às conexões encaminhadas; `api.ipify.org` pode resolver somente para IPv4. Se persistir, teste **no Linux local** `getent ahosts api.ipify.org`, `resolvectl query api.ipify.org` e `curl -v --max-time 15 https://api.ipify.org/`. Para isolar o problema, `curl --socks5 127.0.0.1:1080` na EC2 usa a resolução da própria EC2; esse é apenas um diagnóstico, pois o fluxo normal usa `--socks5-hostname` para encaminhar o nome ao SOCKS5. Consulte os manuais do [OpenSSH](https://man.openbsd.org/ssh) e do [curl](https://curl.se/docs/manpage.html).

Confira `ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" "ss -lnt | grep '127.0.0.1:1080'"`. Encerre o túnel com `Ctrl+C` ao terminar. A porta 1080 deve permanecer acessível apenas no loopback da EC2. O Chromium deve falhar sem fallback direto quando o túnel cair.

Antes de testar o fluxo de apostas, verifique o bloqueio de pagamento. O arquivo é protegido por `root`, portanto use `sudo` apenas para ler a linha necessária:

```bash
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" "sudo grep '^CONFIRM_PAYMENT=' /etc/loto-bot.env"
```

Prossiga somente se a saída for `CONFIRM_PAYMENT=false`. Confira também o parâmetro `ConfirmPayment` da stack; se estiver `true`, um futuro bootstrap poderá voltar a habilitar pagamentos. Com o túnel reverso ativo, execute a validação funcional sem passar credenciais nos comandos:

```bash
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl -i -sSL http://127.0.0.1:8000/api/v1/sessions/status'
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl -fsS --max-time 20 --socks5-hostname 127.0.0.1:1080 https://api.ipify.org >/dev/null'
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl -i -sSL http://127.0.0.1:8000/api/v1/sessions/start'
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl -i -sSL http://127.0.0.1:8000/api/v1/sessions/status'
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl -i -sSL http://127.0.0.1:8000/api/v1/sessions/stop'
aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --query 'Table.{Status:TableStatus,Count:ItemCount}' "${AWS_ARGS[@]}"
```

Para testar as consultas de apostas e o fluxo controlado, use a [seção 12.1 do guia principal](AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md#121-testes-funcionais-sem-inserir-credenciais-nos-comandos) como referência de endpoints; no Linux, use a forma `ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$INSTANCE_IPV6" 'curl ...'`. Resultados e logs podem conter dados de apostas; revise antes de compartilhar.

## 8. Testes descartáveis e limpeza

```bash
./scripts/start-browser-socks5-ipv6-aws.sh --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" --instance-type "$INSTANCE_TYPE"
./scripts/stop-socks5-ipv6-aws.sh
```

Os testes IPv4 alternativos são `start-socks5-ipv4-aws.sh` e `start-browser-socks5-ipv4-aws.sh`; ambos são limpos com `stop-socks5-ipv4-aws.sh`. Se os dois testes IPv4 tiverem arquivos de estado ao mesmo tempo, use `--browser` para limpar o teste Chromium. Se passar `--state-file` na inicialização, passe o mesmo caminho na limpeza. O estado JSON é preservado quando a criação ou a limpeza falha, para permitir nova tentativa. Os arquivos Windows `.ps1` continuam disponíveis.

Para encerrar o ambiente permanente, remova primeiro as stacks consumidoras de rede (`whatsapp-notify`, `gmail-reader`, `mail-sender`) seguindo os respectivos projetos. Confirme os IDs das variáveis desta sessão antes de prosseguir. Em seguida, exclua a stack `loto-bot` e os recursos independentes criados neste guia:

```bash
aws cloudformation delete-stack --stack-name "$STACK_NAME" "${AWS_ARGS[@]}"
aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" "${AWS_ARGS[@]}"
aws ec2 describe-network-interfaces --filters "Name=group-id,Values=$INTEGRATION_GROUP_ID" --query 'NetworkInterfaces[].NetworkInterfaceId' --output table "${AWS_ARGS[@]}"
aws ec2 delete-security-group --group-id "$INTEGRATION_GROUP_ID" "${AWS_ARGS[@]}"
aws ec2 delete-vpc-endpoints --vpc-endpoint-ids "$CFN_ENDPOINT_ID" "${AWS_ARGS[@]}"
for attempt in {1..60}; do
  endpoint_count="$(aws ec2 describe-vpc-endpoints --filters "Name=vpc-endpoint-id,Values=$CFN_ENDPOINT_ID" --query 'length(VpcEndpoints)' --output text "${AWS_ARGS[@]}")"
  [[ "$endpoint_count" == '0' ]] && break
  sleep 5
done
[[ "$endpoint_count" == '0' ]] || { echo 'Endpoint ainda em exclusão' >&2; return 1 2>/dev/null || exit 1; }
aws ec2 delete-security-group --group-id "$CFN_GROUP_ID" "${AWS_ARGS[@]}"
aws ec2 delete-route --route-table-id "$ROUTE_TABLE_ID" --destination-ipv6-cidr-block ::/0 "${AWS_ARGS[@]}"
aws ec2 disassociate-route-table --association-id "$ROUTE_ASSOCIATION_ID" "${AWS_ARGS[@]}"
aws ec2 delete-route-table --route-table-id "$ROUTE_TABLE_ID" "${AWS_ARGS[@]}"
aws ec2 delete-subnet --subnet-id "$SUBNET_ID" "${AWS_ARGS[@]}"
aws ec2 detach-internet-gateway --internet-gateway-id "$INTERNET_GATEWAY_ID" --vpc-id "$VPC_ID" "${AWS_ARGS[@]}"
aws ec2 delete-internet-gateway --internet-gateway-id "$INTERNET_GATEWAY_ID" "${AWS_ARGS[@]}"
aws ec2 delete-vpc --vpc-id "$VPC_ID" "${AWS_ARGS[@]}"
aws ec2 delete-key-pair --key-name "$KEY_NAME" "${AWS_ARGS[@]}"
```

Se houver dependências em uso, pare e investigue o recurso indicado. Remova o segredo da aplicação somente se nenhuma outra stack o usar; `aws secretsmanager delete-secret --secret-id "$APPLICATION_SECRET_ARN" --recovery-window-in-days 7 "${AWS_ARGS[@]}"` mantém uma janela de recuperação. O arquivo PEM local pode ser removido após todas as instâncias que o usam terem sido excluídas. Para o artefato S3, apague somente a chave `$ARTIFACT_KEY` após conferir a stack e o objeto; não use exclusão recursiva do bucket. A [seção 13.2 do guia principal](AWS_FREE_TIER_MIGRATION_STEP_BY_STEP.md#132-remover-a-infraestrutura-criada-neste-guia) detalha essas verificações.

Preserve a tabela DynamoDB se o histórico ainda for necessário. A exclusão permanente requer o comando explícito:

```bash
./scripts/delete-dynamodb-aws.sh --profile "$AWS_PROFILE_NAME" --region "$AWS_REGION" --table "$DYNAMODB_TABLE_NAME" --force
```
