# 연구회 운영위원회 회의자료 생성기 실행 스크립트 (Windows PowerShell)
# 처음 실행 시 가상환경 생성 + 패키지 설치 + PDF용 Chromium 설치까지 자동으로 진행합니다.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"

if (-not (Test-Path ".venv")) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { py -3 -m venv .venv } else { python -m venv .venv }
}
& ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
& ".venv\Scripts\python.exe" -m playwright install chromium

$port = if ($env:MEETING_DOCS_PORT) { $env:MEETING_DOCS_PORT } else { "8766" }
Write-Host ""
Write-Host "브라우저에서 http://localhost:$port 를 여세요. (관리자 초기 계정: admin / admin1234)" -ForegroundColor Cyan
Write-Host "종료: Ctrl+C"
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port $port
