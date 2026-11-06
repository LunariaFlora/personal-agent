$ErrorActionPreference='Stop'
$listeners=Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
    $appProcess=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess)
    if ($appProcess.CommandLine -match '(?:^|\s)-m\s+personal_agent(?:\s|$)' -and $appProcess.CommandLine -match 'PersonalAgent\\runtime\\Scripts\\python.exe') {
        Stop-Process -Id $appProcess.ProcessId
        Write-Host 'Personal Agent 后台已停止。'
    }
}
