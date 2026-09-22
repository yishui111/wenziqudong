# ============================================================
# 文字变声音服务 启动窗口（由 start.bat 打开，前台控制台运行）
# 行为约定（重要，勿再引入自动重启）：
#   1. 只启动一次：本脚本只把 tts_api.py 拉起一次。服务退出后（无论正常
#      退出、报错还是被停止）只打印退出原因，绝不自动重启——
#      再次启动必须由用户重新双击 start.bat。服务只随用户手动启动而启动。
#   2. 写 pid 文件 tmp\tts_service.pid：{ service: 服务PID, started: 启动时间 }
#      （仅作记录；stop.bat 以进程命令行匹配为准，不依赖本文件）
#   3. 关闭本窗口 = 服务一起结束：python 被 Windows Job 对象托管
#      （KILL_ON_JOB_CLOSE），本窗口进程一死，内核立即终止 python 并释放
#      显卡/内存；tts_api.py 内另有父进程看护线程兜底。
#   4. 停止方式任选其一：双击 stop.bat / 关闭本窗口 / 网页「关闭服务」按钮。
# 完全自包含：运行时/ffmpeg 均为项目内置（runtime\py312 / runtime\ffmpeg）
# ============================================================
$ErrorActionPreference = 'Continue'
try { $Host.UI.RawUI.WindowTitle = 'WenZiQuDong 文字变声音 - 关闭此窗口即彻底停止服务(不会自动重启)' } catch {}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = Split-Path -Parent $scriptDir
# 运行时/ffmpeg 均为项目内置（完全自包含，随项目复制即用）
$py        = Join-Path (Join-Path $root 'runtime\py312') 'python.exe'
$api       = Join-Path $scriptDir 'tts_api.py'
$pidFile   = Join-Path $scriptDir 'tmp\tts_service.pid'
$logFile   = Join-Path $scriptDir 'tmp\tts_run.log'

New-Item -ItemType Directory -Force -Path (Split-Path $pidFile) | Out-Null
# 与一键启动 bat 保持一致：ffmpeg 进 PATH（项目内置）
$env:PATH = "$root\runtime\ffmpeg\bin;$env:PATH"

function Write-Log([string]$m) {
    # 日志封顶 1MB：超过则只留最后 200 行，防止无限增长
    if ((Test-Path $logFile) -and ((Get-Item $logFile).Length -gt 1MB)) {
        $tail = Get-Content $logFile -Tail 200 -ErrorAction SilentlyContinue
        Set-Content -Path $logFile -Value $tail -Encoding UTF8
    }
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " " + $m
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line
}

Write-Log "launcher starting (PID=$PID)..."

# Windows Job 对象：本窗口进程退出时内核自动终止其中所有进程（含 python 及其子进程）
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

Write-Log "服务日志实时显示在本窗口；关闭本窗口 = 服务彻底停止，不会自动重启。"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
# -NoNewWindow：python 与本窗口共用控制台，日志实时滚动；文件日志由 tts_api.py 双写
$proc = Start-Process -FilePath $py -ArgumentList @('-u', ('"' + $api + '"')) -NoNewWindow -PassThru
if ($wzdJob -ne [IntPtr]::Zero) {
    try { [void][WzdJob]::AssignProcessToJobObject($wzdJob, $proc.Handle) } catch { Write-Log "job assign failed: $_" }
}
@{
    service = $proc.Id
    started = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
} | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8
Write-Log ("service started (python PID=" + $proc.Id + ")；服务退出后不会自动重启。")
$proc.WaitForExit()
$sw.Stop()
$code = $proc.ExitCode
Write-Log ("service exited (code=" + $code + ", ran " + [int]$sw.Elapsed.TotalSeconds + "s)")
# 把 python 最后 20 行输出写进本日志，便于排查退出原因
$outLog = Join-Path $scriptDir 'tmp\tts_python.log'
if (Test-Path $outLog) {
    $tail = (Get-Content $outLog -Tail 20 -ErrorAction SilentlyContinue) -join ' | '
    if ($tail) { Write-Log ("python 输出末尾: " + $tail) }
}
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
Write-Log "==============================================="
Write-Log "服务已彻底退出（不会自动重启）。"
Write-Log "再次使用请双击 start.bat；本窗口现在可以直接关闭。"
Write-Log "==============================================="
Read-Host "按回车键关闭本窗口"
