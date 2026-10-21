param(
    [Parameter(Mandatory = $true)]
    [string]$AwsProfile,
    [Parameter(Mandatory = $true)]
    [string]$AwsRegion,
    [string]$DynamoDbTableName = "loto-bot-bets",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
if (-not $Force) {
    throw "Exclusao cancelada. Execute novamente com -Force para apagar permanentemente o historico."
}

$AwsCommon = @("--region", $AwsRegion, "--profile", $AwsProfile)
Get-Command aws -ErrorAction Stop | Out-Null
& aws sts get-caller-identity @AwsCommon | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel validar as credenciais AWS." }

$PreviousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $DescribeTableOutput = & aws dynamodb describe-table `
        --table-name $DynamoDbTableName `
        --query "Table.TableName" `
        --output text `
        @AwsCommon 2>&1
    $DescribeTableExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
}

if ($DescribeTableExitCode -eq 0) {
    $ExistingTable = ($DescribeTableOutput | Out-String).Trim()
}
elseif (($DescribeTableOutput | Out-String) -match "ResourceNotFoundException") {
    Write-Host "Tabela DynamoDB '$DynamoDbTableName' nao existe."
    return
}
else {
    $DescribeTableError = ($DescribeTableOutput | Out-String).Trim()
    throw "Falha ao consultar a tabela DynamoDB '$DynamoDbTableName': $DescribeTableError"
}

if ($ExistingTable -ne $DynamoDbTableName) { throw "Resposta inesperada ao consultar a tabela DynamoDB." }

& aws dynamodb delete-table --table-name $DynamoDbTableName @AwsCommon | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falha ao excluir a tabela DynamoDB '$DynamoDbTableName'." }
& aws dynamodb wait table-not-exists --table-name $DynamoDbTableName @AwsCommon
if ($LASTEXITCODE -ne 0) { throw "Falha ao aguardar a exclusao da tabela DynamoDB." }
Write-Host "Tabela DynamoDB '$DynamoDbTableName' excluida permanentemente."
