<#
.SYNOPSIS
  Advisory claim on the game harness (re/harness), so two sessions do not build, inject and
  launch SC3U.exe at the same time.

.DESCRIPTION
  Why this exists: on 2026-08-21 two sessions edited re/harness/src/sc3probe.c and rebuilt it
  within three minutes of each other. The visible symptom was LNK1104 (sc3probe.dll held open by
  an injected process); the real risk is two sessions interleaving edits to a 320 KB source file
  that git does not protect, because re/harness is gitignored.

  A claim file alone is advisory and cannot stop anyone. So -Status also reports the two signals
  that actually matter and cannot be faked:
    * live SC3U / sc3launch processes
    * whether bin/sc3probe.dll is writable (if not, it is injected into a running process)
  Check those before you build. The claim file just tells you WHO to wait for.

  Claim file: re/harness/OWNED_BY.txt (gitignored, local to this machine, by design).

.PARAMETER Status
  Default. Print claim holder, staleness, live processes, DLL lock state.
  Exit 0 = free to use. Exit 1 = held by someone else, or the harness is busy.

.PARAMETER Claim
  Take the claim. Refuses if held by another live owner (use -Force to steal).

.PARAMETER Release
  Release the claim. Refuses to release someone else's unless -Force.

.PARAMETER Owner
  Your session label, e.g. "session-roads" or "harness-session". Defaults to
  SC3_SESSION env var, else "unnamed-$PID".

.PARAMETER Minutes
  Claim lifetime. After this it is reported STALE and may be taken. Default 60.

.EXAMPLE
  pwsh re/scripts/harness_claim.ps1                      # am I clear to build?
  pwsh re/scripts/harness_claim.ps1 -Claim -Owner roads -Note "tilingrules_read_test T0"
  pwsh re/scripts/harness_claim.ps1 -Release -Owner roads
#>
[CmdletBinding(DefaultParameterSetName = 'Status')]
param(
    [Parameter(ParameterSetName = 'Status')]  [switch] $Status,
    [Parameter(ParameterSetName = 'Claim')]   [switch] $Claim,
    [Parameter(ParameterSetName = 'Release')] [switch] $Release,
    [string] $Owner,
    [string] $Note    = "",
    [int]    $Minutes = 60,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'

$repo      = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$harness   = Join-Path $repo "re\harness"
$claimFile = Join-Path $harness "OWNED_BY.txt"
$probeDll  = Join-Path $harness "bin\sc3probe.dll"

if (-not (Test-Path $harness)) { throw "no harness at $harness (wrong repo root?)" }

if (-not $Owner) {
    $Owner = if ($env:SC3_SESSION) { $env:SC3_SESSION } else { "unnamed-$PID" }
}

# ---------------------------------------------------------------- real signals

function Get-GameProcs {
    # -match on ProcessName: SC3U and sc3launch, but not this script.
    @(Get-Process -EA SilentlyContinue |
        Where-Object { $_.ProcessName -match '^(SC3U|sc3launch)$' })
}

function Test-ProbeLocked {
    if (-not (Test-Path $probeDll)) { return $false }
    try {
        # Open for WRITE with no sharing: exactly what the linker needs.
        $s = [IO.File]::Open($probeDll, 'Open', 'Write', 'None')
        $s.Close()
        return $false
    } catch { return $true }
}

# ---------------------------------------------------------------- claim record

function Read-Claim {
    if (-not (Test-Path $claimFile)) { return $null }
    $h = @{}
    foreach ($line in (Get-Content $claimFile -EA SilentlyContinue)) {
        if ($line -match '^\s*([A-Za-z]+)\s*=\s*(.*)$') { $h[$Matches[1].ToLower()] = $Matches[2].Trim() }
    }
    if (-not $h.ContainsKey('owner')) { return $null }

    # $parsed MUST be declared [datetime], not $null: the 4-arg TryParse overload takes an
    # [out] DateTime, and [ref] on an untyped $null resolves to [ref]Object -> no overload found.
    [datetime] $parsed = [datetime]::MinValue
    $claimed = $null
    if ($h.ContainsKey('claimed')) {
        # Round-trip format written below; parse invariantly so a Spanish-locale host reads it back.
        if ([datetime]::TryParse($h['claimed'], [cultureinfo]::InvariantCulture,
                                 [Globalization.DateTimeStyles]::RoundtripKind, [ref]$parsed)) {
            $claimed = $parsed
        }
    }
    $ttl = 60; if ($h.ContainsKey('minutes')) { [int]::TryParse($h['minutes'], [ref]$ttl) | Out-Null }

    $ownerPid = 0
    if ($h.ContainsKey('pid')) { [int]::TryParse($h['pid'], [ref]$ownerPid) | Out-Null }

    # Staleness is TTL-ONLY, deliberately.
    #
    # The obvious extra rule - "stale if the claiming shell died" - is WRONG here and was removed
    # after testing: every invocation of this script is its own short-lived pwsh, so the recorded
    # pid is always gone by the next call. Feeding that into staleness made every claim instantly
    # stealable whenever a game process happened not to be running, which is the exact collision
    # this script exists to prevent. `pid` is kept for diagnostics only.
    $expired = $claimed -and ((Get-Date) -gt $claimed.AddMinutes($ttl))

    [pscustomobject]@{
        Owner = $h['owner']; Note = $(if ($h.ContainsKey('note')) { $h['note'] } else { "" })
        Claimed = $claimed; Minutes = $ttl; Pid = $ownerPid
        Expired = $expired; Stale = $expired
    }
}

function Write-Claim {
    @(
        "# Advisory claim on re/harness. Managed by re/scripts/harness_claim.ps1."
        "# Gitignored and machine-local by design. Delete freely if it is stale."
        "owner   = $Owner"
        "pid     = $PID"
        "claimed = $((Get-Date).ToString('o'))"
        "minutes = $Minutes"
        "note    = $Note"
    ) | Set-Content -Path $claimFile -Encoding utf8
}

# ---------------------------------------------------------------------- report

# Reports on stdout and sets $script:Busy. It must NOT return the verdict, because calling it as
# (Show-Status) would capture every Write-Output line into the return value instead of printing
# it - the whole report vanishes and only the int survives.
$script:Busy = 0

function Show-Status {
    $c     = Read-Claim
    $procs = Get-GameProcs
    $lock  = Test-ProbeLocked

    Write-Output "harness : $harness"
    if ($c) {
        $age = if ($c.Claimed) { "{0:N1} min ago" -f ((Get-Date) - $c.Claimed).TotalMinutes } else { "unknown age" }
        $tag = if ($c.Stale) { "STALE" } else { "ACTIVE" }
        Write-Output "claim   : $tag - '$($c.Owner)' (pid $($c.Pid), $age, ttl $($c.Minutes)m)"
        if ($c.Note)    { Write-Output "note    : $($c.Note)" }
        if ($c.Expired) { Write-Output "          ttl expired - may be taken" }
    } else {
        Write-Output "claim   : none"
    }

    if ($procs.Count) {
        foreach ($p in $procs) {
            Write-Output ("procs   : {0} pid {1} started {2}" -f $p.ProcessName, $p.Id, $p.StartTime)
        }
    } else {
        Write-Output "procs   : no SC3U / sc3launch running"
    }
    Write-Output "probe   : $(if ($lock) { 'LOCKED - injected into a live process, build will fail LNK1104' } else { 'writable - build can link' })"

    $busy = $lock -or $procs.Count -gt 0 -or ($c -and -not $c.Stale -and $c.Owner -ne $Owner)
    Write-Output ""
    if ($busy) {
        Write-Output "VERDICT : BUSY - do not build or launch. Wait, or coordinate with the owner."
        $script:Busy = 1
    } else {
        Write-Output "VERDICT : CLEAR - safe to build and launch (claim it first)."
        $script:Busy = 0
    }
}

# ------------------------------------------------------------------ dispatch

switch ($PSCmdlet.ParameterSetName) {

    'Claim' {
        $c = Read-Claim
        if ($c -and -not $c.Stale -and $c.Owner -ne $Owner -and -not $Force) {
            Show-Status
            Write-Output ""
            Write-Output "REFUSED : '$($c.Owner)' holds an active claim. Use -Force to steal it."
            exit 1
        }
        if ($c -and $c.Owner -ne $Owner) {
            $why = if ($c.Stale) { "stale" } else { "forced" }
            Write-Output "taking over $why claim from '$($c.Owner)'"
        }
        Write-Claim
        Write-Output "CLAIMED : '$Owner' for $Minutes min$(if ($Note) { " - $Note" })"
        # Still surface the real signals: claiming does not make a locked DLL writable.
        Show-Status
        exit 0
    }

    'Release' {
        $c = Read-Claim
        if (-not $c)      { Write-Output "no claim to release"; exit 0 }
        if ($c.Owner -ne $Owner -and -not $Force) {
            Write-Output "REFUSED : claim is held by '$($c.Owner)', not '$Owner'. Use -Force."
            exit 1
        }
        Remove-Item $claimFile -Force
        Write-Output "RELEASED: '$($c.Owner)'"
        exit 0
    }

    default { Show-Status; exit $script:Busy }
}
