$ErrorActionPreference = 'Stop'
$appData = Join-Path (Split-Path -Qualifier $PSScriptRoot) 'AppData\PersonalAgent'
$runtime = Join-Path $appData 'runtime'
$pythonExe = Join-Path $runtime 'Scripts\python.exe'
New-Item -ItemType Directory -Force -Path $appData | Out-Null
$proxySettings = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
if ($proxySettings.ProxyEnable -and $proxySettings.ProxyServer -and $proxySettings.ProxyServer -notmatch '=') {
    if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY='http://'+$proxySettings.ProxyServer }
    if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY=$env:HTTPS_PROXY }
}
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    if (-not (Test-Path -LiteralPath $pythonExe)) { & $uv.Source venv --python python $runtime }
    & $uv.Source pip install --python $pythonExe -r (Join-Path $PSScriptRoot 'requirements.txt')
} else {
    if (-not (Test-Path -LiteralPath $pythonExe)) { python -m venv $runtime }
    & $pythonExe -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
}
if ($LASTEXITCODE -ne 0) { throw '安装失败，请检查网络和 Python 环境。' }
Write-Host '安装完成。双击“启动 Personal Agent.vbs”即可打开。'
