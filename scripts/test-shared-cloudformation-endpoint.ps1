param(
    [Parameter(Mandatory = $true)][string]$AwsProfile,
    [Parameter(Mandatory = $true)][string]$AwsRegion,
    [Parameter(Mandatory = $true)][string]$VpcId
)

$ErrorActionPreference = "Stop"
$serviceName = "com.amazonaws.$AwsRegion.cloudformation"
$result = & aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VpcId" "Name=service-name,Values=$serviceName" --region $AwsRegion --profile $AwsProfile --output json
if ($LASTEXITCODE -ne 0) {
    throw "Não foi possível consultar os endpoints de CloudFormation."
}

$endpoints = @((($result | ConvertFrom-Json).VpcEndpoints) | Where-Object {
    $_.State -eq "available" -and $_.PrivateDnsEnabled -eq $true
})
if ($endpoints.Count -lt 1) {
    throw "A VPC $VpcId precisa de um endpoint CloudFormation disponível com Private DNS antes do deploy EC2."
}

Write-Output "CloudFormation endpoint pronto: $($endpoints[0].VpcEndpointId)"
