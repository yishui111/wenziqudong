# 端口决策（由 start.bat 调用，输出一个端口号）：
#   1) port.txt 记住的端口上跑着本项目的健康服务 -> 沿用它
#   2) 8060 空闲，或上面是本项目服务          -> 用 8060
#   3) 8060 被其他程序占用                     -> 8062..8069 第一个空闲端口
#   4) 全忙                                   -> 输出 0（start.bat 会报错退出）
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pf = Join-Path $root 'tmp\port.txt'
function Get-WzdHealth($p) { try { (Invoke-RestMethod -Uri ('http://127.0.0.1:{0}/health' -f $p) -TimeoutSec 2) } catch { $null } }
$known = ''
if (Test-Path $pf) {
    $known = (Get-Content $pf -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($known) { $known = $known.Trim() }
}
if ($known -match '^\d+$') {
    $h = Get-WzdHealth $known
    if ($h -and $h.service -eq 'wenziqudong-tts') { Write-Output $known; exit }
}
$h = Get-WzdHealth 8060
if (-not $h) { Write-Output 8060; exit }
if ($h.service -eq 'wenziqudong-tts') { Write-Output 8060; exit }
for ($p = 8062; $p -le 8069; $p++) {
    $l = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if (-not $l) { Write-Output $p; exit }
}
Write-Output 0
