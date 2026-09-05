# ============================================================
# 文字驱动语音服务 看门狗（由 一键启动文字驱动语音.bat 调用）
# 功能：
#   1. 启动 tts_api.py（继承 bat 设置的 TTS_DEVICE 环境）
#   2. 写 pid 文件 tts_service\tmp\tts_watchdog.pid：
#      { watchdog: 看门狗自身PID, python: 当前服务PID, started: 启动时间 }
#      - 供关闭脚本定位进程，供启动脚本判断"是否已在启动"
#   3. python 异常退出后 3 秒自动重启；连续 3 次 30 秒内快速退出则
#      退出看门狗（避免死循环，常见原因是 8060 被占用）
# 完全自包含：运行时/ffmpeg 均为项目内置（runtime\py312 / runtime\ffmpeg）
# ============================================================
$ErrorActionPreference = 'Continue'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = Split-Path -Parent $scriptDir
# 运行时/ffmpeg 均为项目内置（完全自包含，随项目复制即用）
$hsRoot    = $root
$py        = Join-Path (Join-Path $root 'runtime\py312') 'python.exe'
$api       = Join-Path $scriptDir 'tts_api.py'
$pidFile   = Join-Path $scriptDir 'tmp\tts_watchdog.pid'
$logFile   = Join-Path $scriptDir 'tmp\tts_watchdog.log'

New-Item -ItemType Directory -Force -Path (Split-Path $pidFile) | Out-Null
# 与一键启动 bat 保持一致：ffmpeg 进 PATH（项目内置）
$env:PATH = "$root\runtime\ffmpeg\bin;$env:PATH"

function Write-Log([string]$m) {
    # 日志封顶 1MB：超过则只留最后 200 行，防止无限增长
    if ((Test-Path $logFile) -and ((Get-Item $logFile).Length -gt 1MB)) {
        $tail = Get-Content $logFile -Tail 200 -ErrorAction SilentlyContinue
        Set-Content -Path $logFile -Value $tail -Encoding UTF8
    }
    Add-Content -Path $logFile -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " " + $m) -Encoding UTF8
}

Write-Log "watchdog started (PID=$PID)"

$quickFail = 0
while ($true) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    # python stdout/stderr 重定向到日志（每次启动覆盖），崩溃/端口冲突原因可查
    $outLog = Join-Path $scriptDir 'tmp\tts_python.log'
    $errLog = $outLog + '.err'
    Remove-Item $outLog, $errLog -Force -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath $py -ArgumentList "`"$api`"" -WindowStyle Minimized -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $info = @{
        watchdog = $PID
        python   = $proc.Id
        started  = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    }
    $info | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8
    Write-Log "service started (python PID=$($proc.Id))"
    $proc.WaitForExit()
    $sw.Stop()
    $code = $proc.ExitCode
    Write-Log "service exited (code=$code, ran $([int]$sw.Elapsed.TotalSeconds)s)"
    # 把 python 最后 20 行输出写入看门狗日志，便于排查
    if (Test-Path $errLog) {
        $tail = (Get-Content $errLog -Tail 20 -ErrorAction SilentlyContinue) -join ' | '
        if ($tail) { Write-Log "python stderr: $tail" }
    }
    if (Test-Path $outLog) {
        $tail2 = (Get-Content $outLog -Tail 5 -ErrorAction SilentlyContinue) -join ' | '
        if ($tail2) { Write-Log "python stdout: $tail2" }
    }

    if ($sw.Elapsed.TotalSeconds -lt 30) { $quickFail++ } else { $quickFail = 0 }
    if ($quickFail -ge 3) {
        Write-Log "3 quick failures, watchdog exits (avoid loop)"
        break
    }
    Start-Sleep -Seconds 3
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
Write-Log "watchdog exit"
