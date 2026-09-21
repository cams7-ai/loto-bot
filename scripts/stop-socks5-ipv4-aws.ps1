[CmdletBinding()]
param(
    [string]$StateFile = (Join-Path $PSScriptRoot "socks5-ipv4-aws-state.json"),
    [string]$AwsProfile,
    [string]$AwsRegion
)

$ErrorActionPreference = "Continue"

# Todas as variáveis usadas na limpeza são inicializadas neste processo.
$TestId = $null
$KeyFile = $null
$KnownHostsFile = $null
$VpcId = $null
$InternetGatewayId = $null
$SubnetId = $null
$RouteTableId = $null
$RouteAssociationId = $null
$SecurityGroupId = $null
$InstanceId = $null
$TunnelProcessId = $null
$CleanupFailed = $false

if (-not (Test-Path -LiteralPath $StateFile)) {
    throw "Arquivo de estado não encontrado: '$StateFile'. Informe o mesmo -StateFile usado na inicialização."
}

$State = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json

$TestId = $State.TestId
$KeyFile = $State.KeyFile
$KnownHostsFile = $State.KnownHostsFile
$VpcId = $State.VpcId
$InternetGatewayId = $State.InternetGatewayId
$SubnetId = $State.SubnetId
$RouteTableId = $State.RouteTableId
$RouteAssociationId = $State.RouteAssociationId
$SecurityGroupId = $State.SecurityGroupId
$InstanceId = $State.InstanceId
$TunnelProcessId = $State.TunnelProcessId

if ([string]::IsNullOrWhiteSpace($AwsProfile)) { $AwsProfile = $State.AwsProfile }
if ([string]::IsNullOrWhiteSpace($AwsRegion)) { $AwsRegion = $State.AwsRegion }

if ([string]::IsNullOrWhiteSpace($TestId)) { throw "O arquivo de estado não contém TestId." }
if ([string]::IsNullOrWhiteSpace($AwsProfile)) { throw "O perfil AWS não foi informado nem encontrado no arquivo de estado." }
if ([string]::IsNullOrWhiteSpace($AwsRegion)) { throw "A região AWS não foi informada nem encontrada no arquivo de estado." }

$AwsCommon = @("--region", $AwsRegion, "--profile", $AwsProfile)

Write-Host "Iniciando limpeza do teste $TestId..."

if ($TunnelProcessId) {
    $TunnelProcess = Get-Process -Id $TunnelProcessId -ErrorAction SilentlyContinue
    if ($TunnelProcess -and $TunnelProcess.ProcessName -in @("ssh", "ssh.exe")) {
        Stop-Process -Id $TunnelProcessId -Force -ErrorAction SilentlyContinue
    }
}

if ($InstanceId) {
    $AwsOutput = & aws ec2 terminate-instances --instance-ids $InstanceId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível solicitar a exclusão da instância $InstanceId."
        $CleanupFailed = $true
    }
    else {
        $AwsOutput = & aws ec2 wait instance-terminated --instance-ids $InstanceId @AwsCommon 2>&1
        $AwsOutput | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "A instância $InstanceId não atingiu o estado terminated no tempo esperado."
            $CleanupFailed = $true
        }
    }
}

if ($SecurityGroupId) {
    $AwsOutput = & aws ec2 delete-security-group --group-id $SecurityGroupId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível excluir o Security Group $SecurityGroupId."
        $CleanupFailed = $true
    }
}

if ($RouteAssociationId) {
    $AwsOutput = & aws ec2 disassociate-route-table --association-id $RouteAssociationId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível desassociar a tabela de rotas ($RouteAssociationId)."
        $CleanupFailed = $true
    }
}

if ($RouteTableId) {
    $AwsOutput = & aws ec2 delete-route-table --route-table-id $RouteTableId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível excluir a tabela de rotas $RouteTableId."
        $CleanupFailed = $true
    }
}

if ($SubnetId) {
    $AwsOutput = & aws ec2 delete-subnet --subnet-id $SubnetId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível excluir a sub-rede $SubnetId."
        $CleanupFailed = $true
    }
}

if ($InternetGatewayId -and $VpcId) {
    $AwsOutput = & aws ec2 detach-internet-gateway `
        --internet-gateway-id $InternetGatewayId --vpc-id $VpcId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível desanexar o Internet Gateway $InternetGatewayId."
        $CleanupFailed = $true
    }
    else {
        $AwsOutput = & aws ec2 delete-internet-gateway `
            --internet-gateway-id $InternetGatewayId @AwsCommon 2>&1
        $AwsOutput | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Não foi possível excluir o Internet Gateway $InternetGatewayId."
            $CleanupFailed = $true
        }
    }
}

if ($VpcId) {
    $AwsOutput = & aws ec2 delete-vpc --vpc-id $VpcId @AwsCommon 2>&1
    $AwsOutput | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Não foi possível excluir a VPC $VpcId."
        $CleanupFailed = $true
    }
}

# O Key Pair deve ser removido mesmo quando a criação da instância tiver falhado.
$AwsOutput = & aws ec2 delete-key-pair --key-name $TestId @AwsCommon 2>&1
$AwsOutput | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Não foi possível excluir o Key Pair $TestId."
    $CleanupFailed = $true
}

if ($KeyFile) { Remove-Item -LiteralPath $KeyFile -Force -ErrorAction SilentlyContinue }
if ($KnownHostsFile) { Remove-Item -LiteralPath $KnownHostsFile -Force -ErrorAction SilentlyContinue }

Write-Host "Confira a auditoria abaixo."
& aws ec2 describe-instances `
    --filters "Name=tag:Name,Values=$TestId" `
    --query "Reservations[].Instances[].{Id:InstanceId,State:State.Name}" `
    --output table @AwsCommon
if ($LASTEXITCODE -ne 0) { $CleanupFailed = $true }

& aws ec2 describe-vpcs `
    --filters "Name=tag:Name,Values=$TestId" `
    --query "Vpcs[].VpcId" --output table @AwsCommon
if ($LASTEXITCODE -ne 0) { $CleanupFailed = $true }

if ($CleanupFailed) {
    Write-Warning "A limpeza terminou com pendências. O arquivo de estado foi mantido para uma nova tentativa: '$StateFile'."
    exit 1
}

Remove-Item -LiteralPath $StateFile -Force
Write-Host "Limpeza concluída. O arquivo de estado local também foi removido."
