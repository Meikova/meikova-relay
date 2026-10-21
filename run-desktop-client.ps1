# Meikova Relay Desktop Client Launcher
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

Start-Process -FilePath $PythonExe -ArgumentList "-m", "client_desktop.desktop_client" -WorkingDirectory $ScriptDir
