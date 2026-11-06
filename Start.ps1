param([switch]$NoWindow)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
$appData = Join-Path (Split-Path -Qualifier $PSScriptRoot) 'AppData\PersonalAgent'
$env:PERSONAL_AGENT_DATA = $appData
$pythonExe = Join-Path $appData 'runtime\Scripts\python.exe'
$appUrl = 'http://127.0.0.1:8765'
New-Item -ItemType Directory -Force -Path (Join-Path $appData 'logs'),(Join-Path $appData 'cache\python') | Out-Null
$env:PYTHONPYCACHEPREFIX = Join-Path $appData 'cache\python'
$env:PYTHONIOENCODING = 'utf-8'
try {
    $alive = Invoke-RestMethod -Uri ($appUrl+'/api/health') -TimeoutSec 2
} catch { $alive = $null }
if (-not $alive -or $alive.app -ne 'PersonalAgent') {
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show('运行环境尚未安装。请运行 Install.ps1 完成安装。','Personal Agent') | Out-Null
        exit 1
    }
    Start-Process -FilePath $pythonExe -ArgumentList '-m','personal_agent' -WorkingDirectory $appRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $appData 'logs\app.out.log') -RedirectStandardError (Join-Path $appData 'logs\app.error.log') | Out-Null
    $ready = $false
    for ($attempt=0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 300
        try {
            $check = Invoke-RestMethod -Uri ($appUrl+'/api/health') -TimeoutSec 1
            if ($check.app -eq 'PersonalAgent') { $ready=$true; break }
        } catch { }
    }
    if (-not $ready) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show('启动未成功，请查看 '+(Join-Path $appData 'logs\app.error.log'),'Personal Agent') | Out-Null
        exit 1
    }
}
if ($NoWindow) { exit 0 }
$chromePaths = @('C:\Program Files\Google\Chrome\Application\chrome.exe','C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',(Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'))
$chromeExe = $chromePaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($chromeExe) { Start-Process -FilePath $chromeExe -ArgumentList ('--app='+$appUrl),'--window-size=1320,880' }
else { Start-Process $appUrl }
