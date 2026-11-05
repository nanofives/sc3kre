<#
  query.ps1 — SimCity 3000 RE  (NO-MCP lookup helpers over re\ghidra_export\)

  These wrap grep over the offline export so "what did the original do?" needs
  zero live Ghidra. Any Claude with Read/Grep can also just grep the files directly.

  Actions:
    -Fn <addr|name>    Show the decompiled C for a function (by 0xADDR or name substring)
    -Xref <name>       Which functions reference this name/symbol (callers)
    -Str <text>        Find defined strings containing <text> (+ their address)
    -Grep <regex>      Raw regex over all decompiled function bodies

  Examples:
    pwsh re\scripts\query.ps1 -Fn 0x004a89f6
    pwsh re\scripts\query.ps1 -Str "RCI"
    pwsh re\scripts\query.ps1 -Xref FUN_004a89f6
    pwsh re\scripts\query.ps1 -Grep "tax|budget"
#>
param([string]$Fn, [string]$Xref, [string]$Str, [string]$Grep)
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Exp  = Join-Path $Root "re\ghidra_export"
$FnDir = Join-Path $Exp "functions"

if ($Fn) {
  $addr = $Fn -replace '^0[xX]', ''   # TrimStart("0x","0X") throws in PowerShell 7 (wants chars)
  $hit = Get-ChildItem $FnDir -Filter "*$addr*.c" -ErrorAction SilentlyContinue
  if (-not $hit) { $hit = Get-ChildItem $FnDir -Filter "*$Fn*.c" -ErrorAction SilentlyContinue }
  if ($hit) { $hit | ForEach-Object { Write-Host "=== $($_.Name) ===" -ForegroundColor Cyan; Get-Content $_.FullName } }
  else { Write-Host "no function file matched '$Fn'" }
}
elseif ($Xref) {
  # Since 2026-11-05 SC3U.exe functions carry their CodeView names, so bodies call cSC3App::GetCity, not
  # FUN_00406270. A FUN_<addr> / 0x<addr> argument is translated to the function's current name first.
  if ($Xref -match '^(?:FUN_|0x)([0-9a-fA-F]{8})$') {
    $want = "0x" + $Matches[1].ToLower()
    $row = Import-Csv (Join-Path $Exp "symbols.csv") | Where-Object { $_.address -eq $want } | Select-Object -First 1
    if ($row -and $row.name -notlike "FUN_*") {
      Write-Host "($want is now '$($row.name)' in namespace '$($row.namespace)'; searching calls to that name)" -ForegroundColor Yellow
      Select-String -Path (Join-Path $FnDir "*.c") -Pattern ("(?<![A-Za-z0-9_])" + [regex]::Escape($row.name) + "\s*\(") |
        Group-Object Filename | ForEach-Object { "{0}  ({1} refs)" -f $_.Name, $_.Count }
      return
    }
  }
  Select-String -Path (Join-Path $FnDir "*.c") -Pattern ([regex]::Escape($Xref)) |
    Group-Object Filename | ForEach-Object { "{0}  ({1} refs)" -f $_.Name, $_.Count }
}
elseif ($Str) {
  Select-String -Path (Join-Path $Exp "strings.csv") -Pattern ([regex]::Escape($Str))
}
elseif ($Grep) {
  Select-String -Path (Join-Path $FnDir "*.c") -Pattern $Grep | Select-Object -First 200
}
else { Write-Host "Specify: -Fn <addr|name> | -Xref <name> | -Str <text> | -Grep <regex>" }
