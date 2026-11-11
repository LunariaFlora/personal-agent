$ErrorActionPreference = 'Stop'
$appData = Join-Path (Split-Path -Qualifier $PSScriptRoot) 'AppData\PersonalAgent'
$pythonExe = Join-Path $appData 'runtime\Scripts\python.exe'
$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $pythonExe -B -m personal_agent.mcp_server
exit $LASTEXITCODE
