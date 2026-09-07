# ============================================================
# 文字驱动语音服务 看门狗（由 start.bat 调用，前台控制台窗口运行）
# 功能：
#   1. 在本窗口前台启动 tts_api.py：服务运行日志实时显示在本窗口
#      （文件日志由 tts_api.py 自己双写 tmp\tts_python.log，每次启动覆盖）
#   2. 写 pid 文件 tts_service\tmp\tts_watchdog.pid：
#      { watchdog: 看门狗PID, python: 服务PID, started: 启动时间 }
#   3. python 异常退出后 3 秒自动重启；连续 3 次 30 秒内快速退出
#      则退出看门狗（避免死循环，常见原因是 8060 被占用）
#   4. **关闭本窗口 = 看门狗 + 服务一起结束**：python 被 Windows Job
#      对象托管（KILL_ON_JOB_CLOSE），看门狗进程一死，内核立即终止
#      python 并释放显卡/内存；tts_api.py 内另有父进程看护线程兜底
# 完全自包含：运行时/ffmpeg 均为项目内置（runtime\py312 / runtime\ffmpeg）
# ============================================================
$ErrorActionPreference = 'Continue'
try { $Host.UI.RawUI.WindowTitle = 'WenZiQuDong 文字驱动语音 - 关闭此窗口即停止服务' } catch {}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = Split-Path -Parent $scriptDir
# 运行时/ffmpeg 均为项目内置（完全自包含，随项目复制即用）
$py        = Join-Path (Join-Path $root 'runtime\py312') 'python.exe'
$api       = Join-Path $scriptDir 'tts_api.py'
$pidFile   = Join-Path $scriptDir 'tmp\tts_watchdog.pid'
$logFile   = Join-Path $scriptDir 'tmp\tts_watchdog.log'

New-Item -ItemType Directory -Force -Path (Split-Path $pidFile) | Out-Null
# 与一键启动 bat 保持一致：ffmpeg 进 PATH（项目内置）
$env:PATH = "$root\runtime\ffmpeg\bin;$env:PATH"

function Write-Log([string]$m) {
    # 看门狗日志封顶 1MB：超过则只留最后 200 行，防止无限增长
    if ((Test-Path $logFile) -and ((Get-Item $logFile).Length -gt 1MB)) {
        $tail = Get-Content $logFile -Tail 200 -ErrorAction SilentlyContinue
        Set-Content -Path $logFile -Value $tail -Encoding UTF8
    }
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " " + $m
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

Write-Log "watchdog starting (PID=$PID)..."

# Windows Job 对象：看门狗进程退出时内核自动终止其中所有进程（含 python 及其子进程）
if (-not ('WzdJob' -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class WzdJob {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr CreateJobObjectW(IntPtr lpJobAttributes, string lpName);
    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct IO_COUNTERS {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetInformationJobObject(IntPtr hJob, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION info, int cbLen);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);
}
"@
}
# 0x2000 = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE（JobObjectExtendedLimitInformation = 9）
$wzdJob = [WzdJob]::CreateJobObjectW([IntPtr]::Zero, $null)
if ($wzdJob -eq [IntPtr]::Zero) {
    Write-Log ("创建 Job 对象失败 errno=" + [Runtime.InteropServices.Marshal]::GetLastWin32Error() + "（关窗口由 tts_api.py 父进程看护兜底）")
} else {
    $wzdJobInfo = New-Object WzdJob+JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    $wzdJobInfo.BasicLimitInformation.LimitFlags = 0x2000
    $wzdJobSize = [System.Runtime.InteropServices.Marshal]::SizeOf($wzdJobInfo)
    if ([WzdJob]::SetInformationJobObject($wzdJob, 9, [ref]$wzdJobInfo, $wzdJobSize)) {
        Write-Log ("job object OK (handle=" + $wzdJob + ")")
    } else {
        Write-Log ("设置 Job 限制失败 errno=" + [Runtime.InteropServices.Marshal]::GetLastWin32Error())
    }
}

Write-Log "服务日志实时显示在本窗口；关闭本窗口 = 看门狗和服务一起停止。"

$quickFail = 0
while ($true) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    # -NoNewWindow：python 与看门狗共用本控制台，日志实时滚动；文件日志由 tts_api.py 双写
    $proc = Start-Process -FilePath $py -ArgumentList @('-u', ('"' + $api + '"')) -NoNewWindow -PassThru
    if ($wzdJob -ne [IntPtr]::Zero) {
        try { [void][WzdJob]::AssignProcessToJobObject($wzdJob, $proc.Handle) } catch { Write-Log "job assign failed: $_" }
    }
    @{
        watchdog = $PID
        python   = $proc.Id
        started  = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    } | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8
    Write-Log ("service started (python PID=" + $proc.Id + ")")
    $proc.WaitForExit()
    $sw.Stop()
    $code = $proc.ExitCode
    Write-Log ("service exited (code=" + $code + ", ran " + [int]$sw.Elapsed.TotalSeconds + "s)")
    # 把 python 最后 20 行输出写入看门狗日志，便于排查
    $outLog = Join-Path $scriptDir 'tmp\tts_python.log'
    if (Test-Path $outLog) {
        $tail = (Get-Content $outLog -Tail 20 -ErrorAction SilentlyContinue) -join ' | '
        if ($tail) { Write-Log ("python 输出末尾: " + $tail) }
    }

    if ($sw.Elapsed.TotalSeconds -lt 30) { $quickFail++ } else { $quickFail = 0 }
    if ($quickFail -ge 3) {
        # 连续快速失败多为显卡/内存被其它程序暂时占用，等一段再试；关闭本窗口随时可停止
        Write-Log "连续 3 次快速失败（多为显卡/内存被其它程序暂时占用），60 秒后继续重试；关闭本窗口即可停止。"
        Start-Sleep -Seconds 60
        $quickFail = 0
    }
    Write-Log "3 秒后自动重启服务..."
    Start-Sleep -Seconds 3
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
Write-Log "watchdog exit"
