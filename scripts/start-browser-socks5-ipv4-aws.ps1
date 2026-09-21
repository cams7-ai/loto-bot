[CmdletBinding()]
param(
    [string]$AwsProfile = "<perfil>",
    [string]$AwsRegion = "us-east-1",
    [string]$InstanceType = "t3.micro",
    [string]$BrowserTestScript = (Join-Path $PSScriptRoot "test_browser_proxy.py"),
    [string]$StateFile = (Join-Path $PSScriptRoot "browser-socks5-ipv4-aws-state.json")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BrowserTestScript -PathType Leaf)) {
    throw "Script de teste do navegador não encontrado: '$BrowserTestScript'."
}

$TestId = "browser-socks5-ipv4-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$MyPublicIp = (curl.exe -fsS https://api.ipify.org).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($MyPublicIp)) {
    throw "Não foi possível descobrir o IP público desta máquina."
}

$MyPublicIpCidr = "$MyPublicIp/32"
$KeyFile = Join-Path $env:TEMP "$TestId.pem"
$KnownHostsFile = Join-Path $env:TEMP "$TestId-known-hosts"
$RemoteUser = "ubuntu"

$VpcId = $null
$InternetGatewayId = $null
$SubnetId = $null
$RouteTableId = $null
$RouteAssociationId = $null
$SecurityGroupId = $null
$InstanceId = $null
$PublicIp = $null
$TunnelProcess = $null
$TunnelProcessId = $null
$Status = "initializing"

$AwsCommon = @("--region", $AwsRegion, "--profile", $AwsProfile)

function Save-State {
    $state = [ordered]@{
        TestId              = $TestId
        AwsProfile          = $AwsProfile
        AwsRegion           = $AwsRegion
        InstanceType        = $InstanceType
        MyPublicIp          = $MyPublicIp
        KeyFile             = $KeyFile
        KnownHostsFile      = $KnownHostsFile
        RemoteUser          = $RemoteUser
        VpcId               = $VpcId
        InternetGatewayId   = $InternetGatewayId
        SubnetId            = $SubnetId
        RouteTableId        = $RouteTableId
        RouteAssociationId  = $RouteAssociationId
        SecurityGroupId     = $SecurityGroupId
        InstanceId          = $InstanceId
        PublicIp            = $PublicIp
        TunnelProcessId     = $TunnelProcessId
        Status              = $Status
        UpdatedAt           = [DateTimeOffset]::UtcNow.ToString("o")
    }

    $state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding utf8
}

if (Test-Path -LiteralPath $StateFile) {
    throw "O arquivo de estado '$StateFile' já existe. Execute primeiro o script de finalização ou informe outro -StateFile."
}

Save-State

try {
    Write-Host "Criando EC2, VPC e demais recursos para o teste $TestId..."
    $AwsOutput = & aws ec2 create-vpc `
        --cidr-block 10.77.0.0/16 `
        --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query Vpc.VpcId --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar a VPC:`n$($AwsOutput -join "`n")" }
    $VpcId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 wait vpc-available --vpc-ids $VpcId @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao aguardar a VPC:`n$($AwsOutput -join "`n")" }

    $AwsOutput = & aws ec2 create-internet-gateway `
        --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query InternetGateway.InternetGatewayId --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar o Internet Gateway:`n$($AwsOutput -join "`n")" }
    $InternetGatewayId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 attach-internet-gateway `
        --internet-gateway-id $InternetGatewayId --vpc-id $VpcId @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao anexar o Internet Gateway:`n$($AwsOutput -join "`n")" }

    $AwsOutput = & aws ec2 describe-availability-zones `
        --filters "Name=state,Values=available" `
        --query "AvailabilityZones[0].ZoneName" --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao consultar a zona de disponibilidade:`n$($AwsOutput -join "`n")" }
    $AvailabilityZone = ($AwsOutput -join "`n").Trim()

    $AwsOutput = & aws ec2 create-subnet `
        --vpc-id $VpcId --cidr-block 10.77.1.0/24 `
        --availability-zone $AvailabilityZone `
        --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query Subnet.SubnetId --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar a sub-rede:`n$($AwsOutput -join "`n")" }
    $SubnetId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 create-route-table `
        --vpc-id $VpcId `
        --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query RouteTable.RouteTableId --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar a tabela de rotas:`n$($AwsOutput -join "`n")" }
    $RouteTableId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 create-route `
        --route-table-id $RouteTableId `
        --destination-cidr-block 0.0.0.0/0 `
        --gateway-id $InternetGatewayId @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar a rota padrão:`n$($AwsOutput -join "`n")" }

    $AwsOutput = & aws ec2 associate-route-table `
        --route-table-id $RouteTableId --subnet-id $SubnetId `
        --query AssociationId --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao associar a tabela de rotas:`n$($AwsOutput -join "`n")" }
    $RouteAssociationId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 create-security-group `
        --group-name $TestId `
        --description "Temporary LotoBot SOCKS5 test" `
        --vpc-id $VpcId `
        --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query GroupId --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar o Security Group:`n$($AwsOutput -join "`n")" }
    $SecurityGroupId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 authorize-security-group-ingress `
        --group-id $SecurityGroupId --protocol tcp --port 22 `
        --cidr $MyPublicIpCidr @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao liberar o SSH:`n$($AwsOutput -join "`n")" }

    & aws ec2 create-key-pair `
        --key-name $TestId `
        --key-type ed25519 `
        --key-format pem `
        --tag-specifications "ResourceType=key-pair,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query "KeyMaterial" `
        --output text `
        @AwsCommon |
        Out-File -FilePath $KeyFile -Encoding ascii

    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o Key Pair '$TestId'." }

    icacls.exe $KeyFile /inheritance:r | Out-Null
    icacls.exe $KeyFile /grant:r "$($env:USERNAME):(R)" | Out-Null

    $AwsOutput = & aws ssm get-parameter `
        --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id `
        --query Parameter.Value --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao consultar a AMI:`n$($AwsOutput -join "`n")" }
    $AmiId = ($AwsOutput -join "`n").Trim()

    $AwsOutput = & aws ec2 run-instances `
        --image-id $AmiId --instance-type $InstanceType `
        --key-name $TestId --subnet-id $SubnetId `
        --security-group-ids $SecurityGroupId `
        --associate-public-ip-address `
        --metadata-options "HttpTokens=required,HttpEndpoint=enabled" `
        --credit-specification "CpuCredits=standard" `
        --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=16,VolumeType=gp3,DeleteOnTermination=true,Encrypted=true}" `
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TestId},{Key=Purpose,Value=ephemeral-test}]" `
        --query "Instances[0].InstanceId" --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao criar a instância:`n$($AwsOutput -join "`n")" }
    $InstanceId = ($AwsOutput -join "`n").Trim()
    Save-State

    $AwsOutput = & aws ec2 wait instance-status-ok --instance-ids $InstanceId @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao aguardar a instância:`n$($AwsOutput -join "`n")" }

    $AwsOutput = & aws ec2 describe-instances `
        --instance-ids $InstanceId `
        --query "Reservations[0].Instances[0].PublicIpAddress" `
        --output text @AwsCommon 2>&1
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI falhou ao consultar o IP da instância:`n$($AwsOutput -join "`n")" }
    $PublicIp = ($AwsOutput -join "`n").Trim()
    Save-State

    $SshOptions = @(
        "-i", $KeyFile,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=$KnownHostsFile",
        "-o", "ConnectTimeout=15"
    )

    Write-Host "Aguardando o SSH responder em $PublicIp..."
    $SshReady = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        Write-Host "Testando SSH ($attempt/30): $RemoteUser@$PublicIp"
        $PreviousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            & ssh @SshOptions "$RemoteUser@$PublicIp" "true" 2>&1 | Out-Null
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

    if (-not $SshReady) { throw "A instância ficou saudável, mas o SSH não respondeu." }

    Write-Host "Instalando Python, Playwright, Chromium e Xvfb na EC2..."
    $ProvisionCommand = @'
set -eu
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv xvfb xauth
python3 -m venv /tmp/lotobot-browser-proxy-venv
/tmp/lotobot-browser-proxy-venv/bin/pip install --quiet playwright
sudo /tmp/lotobot-browser-proxy-venv/bin/python -m playwright install-deps chromium
/tmp/lotobot-browser-proxy-venv/bin/python -m playwright install chromium
'@

    $ProvisionCommand | & ssh @SshOptions "$RemoteUser@$PublicIp" "sed 's/\r$//' | bash -s"
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível preparar Python, Playwright, Chromium e Xvfb na instância."
    }

    & scp @SshOptions -- $BrowserTestScript "${RemoteUser}@${PublicIp}:/tmp/test_browser_proxy.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível enviar '$BrowserTestScript' para a instância."
    }

    # Libera a porta 1080 na EC2, caso exista túnel antigo
    # & ssh @SshOptions "$RemoteUser@$PublicIp" "sudo fuser -k 1080/tcp >/dev/null 2>&1 || true"

    $TunnelArguments = @(
        "-i", $KeyFile,
        "-N", "-T",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=$KnownHostsFile",
        "-R", "127.0.0.1:1080",
        "$RemoteUser@$PublicIp"
    )
    $TunnelProcess = Start-Process ssh -ArgumentList $TunnelArguments -WindowStyle Hidden -PassThru
    $TunnelProcessId = $TunnelProcess.Id
    Save-State
    Start-Sleep -Seconds 5

    if ($TunnelProcess.HasExited) { throw "O processo do túnel SSH terminou antes da validação." }

    $BrowserTestCommand = @'
set -eu
LISTENER="$(ss -lnt | awk '$4 == "127.0.0.1:1080" {print $4}')"
test "$LISTENER" = "127.0.0.1:1080"
printf 'Listener: %s\n' "$LISTENER"
xvfb-run -a env BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080 \
    /tmp/lotobot-browser-proxy-venv/bin/python \
    /tmp/test_browser_proxy.py
'@

    $ValidationOutput = $BrowserTestCommand | & ssh @SshOptions "$RemoteUser@$PublicIp" "sed 's/\r$//' | bash -s"
    $ValidationExitCode = $LASTEXITCODE
    if ($ValidationExitCode -ne 0) {
        throw "Falha ao executar test_browser_proxy.py pelo SOCKS5. Exit code: $ValidationExitCode"
    }
    $ValidationOutput | Out-Host

    $CaixaSuccessLine = $ValidationOutput |
        Where-Object { $_ -eq "Teste CAIXA via Chromium: OK" } |
        Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($CaixaSuccessLine)) {
        throw "test_browser_proxy.py não confirmou o carregamento da página de Termos de Uso da CAIXA."
    }

    Stop-Process -Id $TunnelProcess.Id -Force
    Wait-Process -Id $TunnelProcess.Id -ErrorAction SilentlyContinue
    $TunnelProcess = $null
    $TunnelProcessId = $null
    Save-State

    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $FailClosedOutput = & ssh @SshOptions "$RemoteUser@$PublicIp" `
            "timeout 45s xvfb-run -a env BROWSER_PROXY_SERVER=socks5://127.0.0.1:1080 /tmp/lotobot-browser-proxy-venv/bin/python /tmp/test_browser_proxy.py" 2>&1
        $FailClosedExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }

    if ($FailClosedExitCode -eq 0) {
        $FailClosedOutput | Out-Host
        throw "O teste fail-closed falhou: o Chromium navegou após encerrar o túnel."
    }

    Write-Host "Falha sem fallback confirmada após encerrar o túnel."

    $Status = "ready-for-cleanup"
    Save-State

    Write-Host "Teste aprovado: a página de Termos de Uso da CAIXA abriu pelo SOCKS5 e falhou sem fallback."
    Write-Host "Os recursos continuam ativos. Para apagá-los, execute:"
    Write-Host ".\stop-socks5-aws.ps1 -StateFile `"$StateFile`""
}
catch {
    $Status = "initialization-failed"
    Save-State

    Write-Error "A inicialização falhou. O estado foi preservado em '$StateFile'. Execute o script de finalização para remover os recursos já criados. Erro: $($_.Exception.Message)"
}
