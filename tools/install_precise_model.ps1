param(
    [string]$Destination = (Join-Path (Split-Path -Parent $PSScriptRoot) "backend\models\faster-whisper-large-v3")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$vendorRoot = Join-Path $PSScriptRoot "vendor"
$ariaRoot = Join-Path $vendorRoot "aria2-1.37.0-win-64bit-build1"
$aria = Join-Path $ariaRoot "aria2c.exe"
$ariaArchive = Join-Path $vendorRoot "aria2.zip"
$modelUrl = "https://www.modelscope.cn/api/v1/models/Systran/faster-whisper-large-v3/repo?Revision=master&FilePath=model.bin"
$expectedBytes = 3087284237
$expectedSha256 = "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1"

New-Item -ItemType Directory -Path $vendorRoot -Force | Out-Null
New-Item -ItemType Directory -Path $Destination -Force | Out-Null

if (-not (Test-Path -LiteralPath $aria -PathType Leaf)) {
    Write-Host "下载 aria2 1.37.0..." -ForegroundColor Cyan
    $downloadArguments = @{
        Uri = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
        OutFile = $ariaArchive
    }
    Invoke-WebRequest @downloadArguments
    Expand-Archive -LiteralPath $ariaArchive -DestinationPath $vendorRoot -Force
}

$modelPath = Join-Path $Destination "model.bin"
Write-Host "下载 faster-whisper large-v3（支持断点续传）..." -ForegroundColor Cyan
& $aria --continue=true --max-connection-per-server=16 --split=16 --min-split-size=8M --file-allocation=none --max-tries=0 --retry-wait=3 --timeout=60 --dir=$Destination --out="model.bin" $modelUrl
if ($LASTEXITCODE -ne 0) {
    throw "large-v3 下载失败，aria2 退出码：$LASTEXITCODE"
}

$modelFile = Get-Item -LiteralPath $modelPath
if ($modelFile.Length -ne $expectedBytes) {
    throw "large-v3 文件大小错误：$($modelFile.Length)，预期：$expectedBytes"
}
$actualSha256 = (Get-FileHash -LiteralPath $modelPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $expectedSha256) {
    throw "large-v3 SHA256 校验失败，禁止启用精准模式"
}

$metadataFiles = @(
    "config.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "vocabulary.json"
)
foreach ($name in $metadataFiles) {
    $target = Join-Path $Destination $name
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        $encodedName = [Uri]::EscapeDataString($name)
        $metadataArguments = @{
            Uri = "https://www.modelscope.cn/api/v1/models/Systran/faster-whisper-large-v3/repo?Revision=master&FilePath=$encodedName"
            OutFile = $target
        }
        Invoke-WebRequest @metadataArguments
    }
}

Write-Host "精准模型安装并校验完成：$Destination" -ForegroundColor Green
