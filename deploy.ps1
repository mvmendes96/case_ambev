# deploy.ps1 - Script PowerShell para deploy
param(
    [string]$Environment = "dev"
)

# Configurações
$ProjectId = "ambev-2025"
$Region = "us-central1"

# Função de log
function Write-Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] WARN: $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $Message" -ForegroundColor Red
}

# Validar ambiente
if ($Environment -notin @("dev", "staging", "prod")) {
    Write-Error "Ambiente inválido: $Environment. Use: dev, staging, prod"
    exit 1
}

Write-Log "Iniciando deploy no ambiente: $Environment"
Write-Log "Projeto: $ProjectId"
Write-Log "Região: $Region"

# Build e push de uma imagem específica
function Build-Image {
    param(
        [string]$Layer,
        [string]$Dockerfile
    )
    
    Write-Log "Construindo imagem Docker para $Layer..."
    Write-Log "Usando Dockerfile: $Dockerfile"
    
    # Copiar o Dockerfile específico para Dockerfile temporário
    Copy-Item -Path $Dockerfile -Destination "Dockerfile" -Force
    
    gcloud builds submit --tag "gcr.io/$ProjectId/etl-$Layer" --project=$ProjectId
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha no build da imagem $Layer"
        exit 1
    }
    
    Write-Log "Imagem $Layer construída com sucesso!"
}

# Verificar se Dockerfiles existem
$dockerfiles = @{
    "bronze" = "Dockerfile.bronze"
    "silver" = "Dockerfile.silver" 
    "gold" = "Dockerfile.gold"
}

foreach ($layer in $dockerfiles.Keys) {
    $dockerfile = $dockerfiles[$layer]
    if (-not (Test-Path $dockerfile)) {
        Write-Error "Dockerfile não encontrado: $dockerfile"
        exit 1
    }
}

# Build das imagens
foreach ($layer in $dockerfiles.Keys) {
    Build-Image -Layer $layer -Dockerfile $dockerfiles[$layer]
}

# Aplicar Terraform
if (Test-Path "terraform") {
    Write-Log "Aplicando configurações do Terraform..."
    Set-Location "terraform"
    terraform init -upgrade
    terraform apply -var="environment=$Environment" -auto-approve
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha na aplicação do Terraform"
        exit 1
    }
    Set-Location ".."
} else {
    Write-Warning "Diretório terraform/ não encontrado"
}

Write-Log "Deploy concluído com sucesso!"
Write-Log "Imagens deployadas:"
Write-Host "  - gcr.io/$ProjectId/etl-bronze"
Write-Host "  - gcr.io/$ProjectId/etl-silver" 
Write-Host "  - gcr.io/$ProjectId/etl-gold"
Write-Host ""
Write-Log "Jobs Cloud Run criados:"
Write-Host "  - etl-bronze-job-$Environment"
Write-Host "  - etl-silver-job-$Environment"
Write-Host "  - etl-gold-job-$Environment"