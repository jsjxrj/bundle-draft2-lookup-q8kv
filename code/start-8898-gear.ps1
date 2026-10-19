# Workbench gear: Bonsai bundle 262K, MTP draft2 + lookup32 + q8_0 KV, port 8898.
# 2026-10-19 measured best-stable gear (ski-game probe: 48.7 tok/s, complete output).
param([string]$Think = '1')
$ErrorActionPreference = 'Stop'
# Deduplicate proxy vars first: PowerShell 5.1 Get-ChildItem Env: throws
# "An item with the same key has already been added" when the env block holds
# both HTTP_PROXY and http_proxy (crashes the bundle launcher at line 6).
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
$env:BONSAI_PORT = '8898'
$env:BONSAI_SPEC = '2'      # MTP draft 2 (8GB best)
$env:BONSAI_CTK = 'q8_0'    # q8_0 K/V (+ -ctvd via launcher)
$env:BONSAI_THINK = if ($Think -eq '0') { '0' } else { '1' }
Set-Location 'E:\Code\AI\bonsai-local\262k-bundle\bundle'
& .\start-server-local.ps1
