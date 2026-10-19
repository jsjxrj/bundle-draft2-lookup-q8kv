# Bundle draft gear test wrapper: BONSAI_SPEC=<draft>, lookup 32, q8_0 KV, port 8898
param([string]$Draft = '2')
$ErrorActionPreference = 'Stop'
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
$env:BONSAI_PORT = '8898'
$env:BONSAI_SPEC = $Draft
$env:BONSAI_CTK = 'q8_0'
$env:BONSAI_THINK = '0'
Set-Location 'E:\Code\AI\bonsai-local\262k-bundle\bundle'
& .\start-server-local.ps1
