# serve.ps1 — 폴더 하나를 로컬 서버로 띄워 이 PC와 같은 Wi-Fi의 폰에서 본다.
#
# 언제: 정적 앱 · 문서 뷰어를 폰에서 직접 눌러 보고 싶을 때. (Claude가 시험용으로 잠깐 띄우는 서버는
#       screen-test의 check.mjs --dir 가 맡는다. 이 script는 사람이 보는 용도다.)
# kind: utility
# status: active
#
# 사용:
#   powershell -ExecutionPolicy Bypass -File serve.ps1 -Root <폴더> [-Port 8000] [-Path ideas/] [-NewWindow] [-Force]
#     -Root       띄울 폴더 (기본: 지금 폴더)
#     -Port       포트 (기본 8000)
#     -Path       안내할 시작 주소의 하위 경로 (예: ideas/)
#     -NewWindow  새 PowerShell 창에서 띄운다 (Claude 세션 · 이 터미널을 닫아도 계속 돈다)
#     -Force      포트를 이미 쓰는 프로세스를 끄고 띄운다 (기본은 알려 주고 멈춘다)
# 종료: 서버 창에서 Ctrl+C
#
# 한글 깨짐 방지: .html · .md · .js · .mjs · .css · .json · .txt 를 charset=utf-8 로 보낸다. 캐시는 끈다(no-store).
# 이 파일은 UTF-8 BOM으로 저장한다(PowerShell 5.1은 BOM 없는 .ps1을 cp949로 읽어 한글이 깨진다).

param(
  [string]$Root = (Get-Location).Path,
  [int]$Port = 8000,
  [string]$Path = '',
  [switch]$NewWindow,
  [switch]$Force
)
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path -LiteralPath $Root).Path
$Path = $Path.TrimStart('/')

if ($NewWindow) {
  $argList = @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Root', "`"$Root`"", '-Port', $Port)
  if ($Path) { $argList += @('-Path', $Path) }
  if ($Force) { $argList += '-Force' }
  Start-Process powershell -ArgumentList $argList | Out-Null
  Write-Host "새 창에서 서버를 띄웠다: http://localhost:$Port/$Path"
  exit 0
}

# 포트를 이미 쓰고 있나
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) {
  $procIds = @($busy | Select-Object -ExpandProperty OwningProcess -Unique)
  if (-not $Force) {
    $names = ($procIds | ForEach-Object { (Get-Process -Id $_ -ErrorAction SilentlyContinue).ProcessName }) -join ', '
    Write-Host "포트 $Port 를 이미 쓰는 프로세스가 있다: $names (PID $($procIds -join ', ')). -Port 로 바꾸거나 -Force 로 끄고 띄운다." -ForegroundColor Yellow
    exit 1
  }
  foreach ($procId in $procIds) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 500
}

# LAN IP (폰 주소)
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.*' } |
  Select-Object -First 1).IPAddress
if (-not $ip) { $ip = 'localhost' }

Write-Host ""
Write-Host " 폴더            : $Root" -ForegroundColor Cyan
Write-Host " 이 PC           : http://localhost:$Port/$Path" -ForegroundColor White
Write-Host " 폰(같은 Wi-Fi)  : http://${ip}:$Port/$Path" -ForegroundColor Green
Write-Host " 종료            : Ctrl+C" -ForegroundColor DarkGray
try { Set-Clipboard -Value "http://${ip}:$Port/$Path"; Write-Host " 폰 주소를 클립보드에 복사했다" -ForegroundColor DarkGray } catch {}
Write-Host ""

$server = @'
import functools, http.server, sys
port, root = int(sys.argv[1]), sys.argv[2]
U = '; charset=utf-8'
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
        '.html': 'text/html' + U, '.htm': 'text/html' + U, '.md': 'text/markdown' + U,
        '.js': 'text/javascript' + U, '.mjs': 'text/javascript' + U, '.css': 'text/css' + U,
        '.json': 'application/json' + U, '.txt': 'text/plain' + U, '.svg': 'image/svg+xml',
        '.webmanifest': 'application/manifest+json', '.wasm': 'application/wasm'}
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
http.server.ThreadingHTTPServer(('0.0.0.0', port), functools.partial(Handler, directory=root)).serve_forever()
'@

$env:PYTHONIOENCODING = 'utf-8'
$server | python - $Port $Root
