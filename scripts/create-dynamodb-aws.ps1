param(
    [Parameter(Mandatory = $true)]
    [string]$AwsProfile,
    [Parameter(Mandatory = $true)]
    [string]$AwsRegion,
    [string]$DynamoDbTableName = "loto-bot-bets"
)

$ErrorActionPreference = "Stop"
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
    $ExistingTable = $null
}
else {
    $DescribeTableError = ($DescribeTableOutput | Out-String).Trim()
    throw "Falha ao consultar a tabela DynamoDB '$DynamoDbTableName': $DescribeTableError"
}

if ($null -eq $ExistingTable) {
    & aws dynamodb create-table `
        --table-name $DynamoDbTableName `
        --attribute-definitions AttributeName=bet_id,AttributeType=S `
        --key-schema AttributeName=bet_id,KeyType=HASH `
        --billing-mode PAY_PER_REQUEST `
        --tags Key=Application,Value=loto-bot Key=Environment,Value=aws Key=ManagedBy,Value=script Key=Purpose,Value=bet-history `
        @AwsCommon | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar a tabela DynamoDB '$DynamoDbTableName'." }
}
elseif ($ExistingTable -ne $DynamoDbTableName) {
    throw "Resposta inesperada ao consultar a tabela DynamoDB."
}

& aws dynamodb wait table-exists --table-name $DynamoDbTableName @AwsCommon
if ($LASTEXITCODE -ne 0) { throw "Falha ao aguardar a tabela DynamoDB." }

$TableStatus = & aws dynamodb describe-table --table-name $DynamoDbTableName --query "Table.TableStatus" --output text @AwsCommon
$HashKey = & aws dynamodb describe-table --table-name $DynamoDbTableName --query "Table.KeySchema[?KeyType=='HASH'].AttributeName | [0]" --output text @AwsCommon
$BillingMode = & aws dynamodb describe-table --table-name $DynamoDbTableName --query "Table.BillingModeSummary.BillingMode" --output text @AwsCommon
if ($TableStatus -ne "ACTIVE") { throw "Tabela DynamoDB nao esta ACTIVE: $TableStatus" }
if ($HashKey -ne "bet_id") { throw "Tabela DynamoDB '$DynamoDbTableName' possui Partition Key incompativel: '$HashKey'." }
if ($BillingMode -ne "PAY_PER_REQUEST") {
    throw "Tabela DynamoDB '$DynamoDbTableName' possui Billing Mode incompativel: '$BillingMode'. Esperado: PAY_PER_REQUEST."
}

$TableArn = & aws dynamodb describe-table --table-name $DynamoDbTableName --query "Table.TableArn" --output text @AwsCommon
& aws dynamodb tag-resource --resource-arn $TableArn --tags Key=Application,Value=loto-bot Key=Environment,Value=aws Key=ManagedBy,Value=script Key=Purpose,Value=bet-history @AwsCommon
if ($LASTEXITCODE -ne 0) { throw "Falha ao garantir as tags da tabela DynamoDB." }

Write-Host "DynamoDB table: $DynamoDbTableName"
Write-Host "Status: $TableStatus"
Write-Host "Billing mode: $BillingMode"
Write-Host "Region: $AwsRegion"
Write-Output $DynamoDbTableName
