# Chrome Profile Hub - Windows installer (per machine, no admin rights needed for your own Start Menu)
# Usage:  powershell -ExecutionPolicy Bypass -File install.ps1 [-AllUsers] [-Lang vi]
param([switch]$AllUsers, [string]$Lang = "")
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = (Get-Command python -ErrorAction Stop).Source
$pyw = Join-Path (Split-Path $py) "pythonw.exe"
& $py -m pip install --quiet -r (Join-Path $repo "requirements.txt")

# config file (created once, never overwritten)
$cfgDir = Join-Path $env:APPDATA "ChromeProfileHub"; New-Item -ItemType Directory -Force $cfgDir | Out-Null
$cfg = Join-Path $cfgDir "config.json"
if (-not (Test-Path $cfg)) {
  Copy-Item (Join-Path $repo "config.example.json") $cfg
  if ($Lang) { (Get-Content $cfg -Raw) -replace '"lang": "en"', ('"lang": "' + $Lang + '"') | Set-Content $cfg -Encoding UTF8 }
  Write-Host "Created $cfg - edit it to add your existing profile folders."
}

$menu = if ($AllUsers) { Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs" } else { Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs" }
$desk = [Environment]::GetFolderPath("Desktop")
$sh = New-Object -ComObject WScript.Shell
foreach ($dir in @($menu, $desk)) {
  $l = $sh.CreateShortcut((Join-Path $dir "Chrome Profile Hub.lnk"))
  $l.TargetPath = $pyw; $l.Arguments = "-m chrome_profile_hub"; $l.WorkingDirectory = $repo
  $l.IconLocation = (Join-Path $repo "assets\icon.ico"); $l.Description = "Chrome profiles shared by humans and AI agents"; $l.Save()
}
Write-Host "Done. Start Menu / Desktop: 'Chrome Profile Hub'"
