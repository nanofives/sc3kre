<#
.SYNOPSIS
    SimCity 3000 dev build: LAN auto-updater (copy of TD5RE's td5re_update.ps1, adapted).

.DESCRIPTION
    Downloads manifest.json from the mini-server, compares the SHA-256 of every file already in this folder and
    downloads ONLY what is missing or changed. Safe to run as often as you like. Close the game first: a running
    game locks its DLLs.

    Never overwritten (manifest "seed" entries, downloaded only when missing): the game's own preferences
    (Apps\SC3.cfg, Apps\SC3Net.cfg) and Apps\SC3U.ini. Your saved cities are not in the manifest and are never touched.

    -Prune also deletes files under mods\netmod\ that the server no longer has (road packages that were removed).

.USAGE
    Double-click update.bat, or:
        powershell -ExecutionPolicy Bypass -File sc3_update.ps1 [-BaseUrl http://192.168.68.112:8088/simcity] [-Prune]
#>
[CmdletBinding()]
param(
    [string[]]$BaseUrl,
    [string]$InstallRoot = $PSScriptRoot,
    [switch]$Prune
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

if (-not $InstallRoot) { $InstallRoot = (Get-Location).Path }
if (-not $BaseUrl -or $BaseUrl.Count -eq 0) {
    # the .local name on a flat LAN; the Pi's static IP when mDNS cannot cross a second router
    $BaseUrl = @('http://mariano-server.local:8088/simcity', 'http://192.168.68.112:8088/simcity')
}
$BaseUrl = @($BaseUrl | ForEach-Object { $_.TrimEnd('/') })

function Url-For([string]$rel) {
    $enc = ($rel -split '/' | ForEach-Object { [uri]::EscapeDataString($_) }) -join '/'
    return "$script:ResolvedBase/$enc"
}

# .NET SHA-256: some Windows PowerShell 5.1 installs lack Get-FileHash (seen on the TD5RE machines)
function Get-Sha256Hex([string]$full) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $fs = [System.IO.File]::OpenRead($full)
        try { $bytes = $sha.ComputeHash($fs) } finally { $fs.Dispose() }
    } finally { $sha.Dispose() }
    -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

Write-Host ""
Write-Host "SimCity 3000 dev build updater" -ForegroundColor Cyan
Write-Host ("  servers: {0}" -f ($BaseUrl -join ', '))
Write-Host "  target : $InstallRoot"

if (Get-Process -Name 'SC3U', 'SC3U_mods' -ErrorAction SilentlyContinue) {
    Write-Host "ERROR: SimCity 3000 is running. Close it and run the update again." -ForegroundColor Red
    exit 1
}

# --- 1. manifest -------------------------------------------------------------------------------------------------
$script:ResolvedBase = $null
$manifest = $null
$tmpManifest = Join-Path ([System.IO.Path]::GetTempPath()) ("sc3_manifest_" + [guid]::NewGuid().ToString("N") + ".json")
foreach ($base in $BaseUrl) {
    try {
        Invoke-WebRequest -Uri "$base/manifest.json" -OutFile $tmpManifest -UseBasicParsing -TimeoutSec 30
        $candidate = (Get-Content -LiteralPath $tmpManifest -Raw -Encoding UTF8) | ConvertFrom-Json
        if (@($candidate.files).Count -ge 1 -and $candidate.files[0].path) {
            $script:ResolvedBase = $base
            $manifest = $candidate
            Write-Host ("  server : {0}" -f $base) -ForegroundColor Green
            break
        }
        Write-Host ("  ! {0}/manifest.json is not a valid manifest, trying next ..." -f $base) -ForegroundColor DarkYellow
    } catch {
        Write-Host ("  ! {0} unreachable ({1}), trying next ..." -f $base, $_.Exception.Message) -ForegroundColor DarkYellow
    }
}
if (Test-Path -LiteralPath $tmpManifest) { Remove-Item -LiteralPath $tmpManifest -Force -ErrorAction SilentlyContinue }
if (-not $manifest) {
    Write-Host "ERROR: no server answered with a manifest. Tried:" -ForegroundColor Red
    foreach ($base in $BaseUrl) { Write-Host "       $base/manifest.json" -ForegroundColor Red }
    exit 1
}
$files = @($manifest.files)
Write-Host ("  build  : {0} ({1} files, generated {2})" -f $manifest.label, $files.Count, $manifest.generated)

# --- 2. what to download ------------------------------------------------------------------------------------------
$toGet = New-Object System.Collections.Generic.List[object]
$upToDate = 0
foreach ($f in $files) {
    $local = Join-Path $InstallRoot ($f.path -replace '/', '\')
    $need = $true
    if (Test-Path -LiteralPath $local) {
        if ($f.seed) { $need = $false }
        elseif ((Get-Item -LiteralPath $local).Length -eq [int64]$f.size -and (Get-Sha256Hex $local) -ieq $f.sha256) { $need = $false }
    }
    if ($need) { $toGet.Add($f) } else { $upToDate++ }
}
$mb = ($toGet | Measure-Object -Property size -Sum).Sum / 1MB
Write-Host ("  up to date: {0}   to download: {1} ({2:N1} MB)" -f $upToDate, $toGet.Count, $mb) -ForegroundColor Green

# --- 3. download ------------------------------------------------------------------------------------------------
$done = 0; $failed = 0; $i = 0
foreach ($f in $toGet) {
    $i++
    $local = Join-Path $InstallRoot ($f.path -replace '/', '\')
    $dir = Split-Path -Parent $local
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = "$local.dl_tmp"
    Write-Host ("  [{0}/{1}] {2}" -f $i, $toGet.Count, $f.path)
    try {
        Invoke-WebRequest -Uri (Url-For $f.path) -OutFile $tmp -UseBasicParsing -TimeoutSec 600
        if ((Get-Sha256Hex $tmp) -ine $f.sha256) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            Write-Host "      ! hash mismatch after download, skipped" -ForegroundColor Red
            $failed++
            continue
        }
        Move-Item -LiteralPath $tmp -Destination $local -Force
        $done++
    } catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Write-Host "      ! download failed: $($_.Exception.Message)" -ForegroundColor Red
        $failed++
    }
}

# --- 4. optional prune: only mods\netmod (package files), never Apps or Cities ----------------------------------
$pruned = 0
if ($Prune) {
    $keep = New-Object System.Collections.Generic.HashSet[string]
    foreach ($f in $files) { [void]$keep.Add((Join-Path $InstallRoot ($f.path -replace '/', '\')).ToLower()) }
    $netmod = Join-Path $InstallRoot 'mods\netmod'
    if (Test-Path -LiteralPath $netmod) {
        Get-ChildItem -LiteralPath $netmod -Recurse -File | ForEach-Object {
            if (-not $keep.Contains($_.FullName.ToLower())) {
                Remove-Item -LiteralPath $_.FullName -Force
                Write-Host ("  - pruned {0}" -f $_.FullName.Substring($InstallRoot.Length + 1)) -ForegroundColor DarkYellow
                $pruned++
            }
        }
    }
}

Write-Host ""
Write-Host ("Done. updated {0}, up to date {1}, failed {2}, pruned {3}." -f $done, $upToDate, $failed, $pruned) -ForegroundColor Cyan
Write-Host "Start the game with 'Jugar SimCity (mods).bat'."
if ($failed -gt 0) { exit 1 }
exit 0
