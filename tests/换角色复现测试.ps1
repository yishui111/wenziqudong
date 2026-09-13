# 换角色合成复现测试：逐个角色首次加载合成，监控服务是否崩溃/报错
# 角色列表自动取自服务 /models（第一个可用角色起逐个测试，不限于写死的角色名）
# 用法：pwsh -File tests\换角色复现测试.ps1
$ErrorActionPreference = 'Continue'
$base = 'http://127.0.0.1:18062'
$logFile = Join-Path $PSScriptRoot '换角色测试结果.txt'
Remove-Item $logFile -ErrorAction SilentlyContinue
Add-Content $logFile ("换角色合成测试 " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -Encoding UTF8

try {
    $models = (Invoke-RestMethod "$base/models" -TimeoutSec 10).models
} catch {
    Add-Content $logFile ("无法连接服务 $base : " + $_.Exception.Message) -Encoding UTF8
    Write-Output "无法连接服务 $base ，请先启动服务（一键启动文字驱动语音.bat）"
    exit 1
}
$roles = @($models | Where-Object { $_.ready } | ForEach-Object { $_.name })
if ($roles.Count -eq 0) {
    Add-Content $logFile '没有任何可用角色（需先放置音色模型 4 件套）' -Encoding UTF8
    Write-Output "没有任何可用角色"
    exit 1
}
Write-Output ("测试角色: " + ($roles -join ', '))

foreach ($r in $roles) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $resp = Invoke-WebRequest -Uri "$base/tts" -Method Post -Body @{ text = '大家好，这是一次换角色测试。'; character = $r; speed = '1.0' } -TimeoutSec 600
        $sw.Stop()
        $line = "[OK] $r : $([int]$sw.Elapsed.TotalSeconds)s, $($resp.RawContentLength) bytes"
        Write-Output $line
        Add-Content $logFile $line -Encoding UTF8
    } catch {
        $sw.Stop()
        $line = "[FAIL] $r : $([int]$sw.Elapsed.TotalSeconds)s, $($_.Exception.Message)"
        Write-Output $line
        Add-Content $logFile $line -Encoding UTF8
        # 服务是否还活着？
        try { $h = Invoke-RestMethod "$base/health" -TimeoutSec 5; Add-Content $logFile "   health: $($h.status)" -Encoding UTF8 } catch { Add-Content $logFile "   health: 连接失败（服务可能崩溃/重启中）" -Encoding UTF8 }
    }
    Start-Sleep -Seconds 2
}
Write-Output "完成，结果见 $logFile"
