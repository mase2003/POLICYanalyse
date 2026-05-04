# 在「仅含 backend/requirements.txt」的虚拟环境中用 PyInstaller 打 Windows exe，
# 避免使用全局 Python 时把 torch / TensorFlow / IPython 等一并打进包（体积巨大且易失败）。
# 用法：在仓库根目录执行: powershell -ExecutionPolicy Bypass -File scripts\build_backend_exe.ps1
#
# WinError 32「另一个程序正在使用此文件」常见原因：neo4j-vis-api.exe 仍在运行、资源管理器预览、杀软扫描。
# 脚本会先尝试结束本机上的 neo4j-vis-api 进程，并重试删除 backend\build。

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv-build"
$Py = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"
$BuildWork = Join-Path $Backend "build\neo4j-vis-api"

function Stop-Neo4jVisApiProcesses {
    Get-Process -Name "neo4j-vis-api" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Stopping process locking the build (PID $($_.Id)): neo4j-vis-api"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 800
}

function Remove-PathRetry {
    param(
        [string]$Path,
        [int]$Retries = 6
    )
    if (-not (Test-Path $Path)) { return }
    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            Write-Warning "Cannot remove yet (attempt $($i + 1)/${Retries}): $Path — $($_.Exception.Message)"
            Stop-Neo4jVisApiProcesses
            Start-Sleep -Seconds 2
        }
    }
    throw "Still locked: $Path. Close neo4j-vis-api.exe, turn off preview in Explorer, or retry after antivirus finishes."
}

Set-Location $Backend

if (-not (Test-Path $Py)) {
    Write-Host "Creating venv at $Venv ..."
    & python -m venv $Venv
}

$Pypi = "https://pypi.org/simple/"
Write-Host "Installing dependencies (PyPI: $Pypi) ..."
& $Pip install -q --upgrade pip
& $Pip install -q -r requirements.txt -i $Pypi
& $Pip install -q pyinstaller -i $Pypi

Write-Host "Preparing clean build folder ..."
Stop-Neo4jVisApiProcesses
Remove-PathRetry -Path (Join-Path $Backend "build")

Write-Host "Building neo4j-vis-api.exe (one-file) ..."
& $Py -m PyInstaller --noconfirm --clean neo4j-vis-api.spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller exited with code $LASTEXITCODE. If you see WinError 32, stop neo4j-vis-api.exe and run this script again."
    exit $LASTEXITCODE
}

$Out = Join-Path $Backend "dist\neo4j-vis-api.exe"
if (-not (Test-Path $Out)) {
    Write-Error "Build failed: $Out not found after successful PyInstaller exit."
    exit 1
}

Write-Host "OK: $Out"
