<#
PowerShell build script for Windows
Run this from the repo's build directory (.
Example: cd C:\path\to\repo\build; .\build_exe.ps1
It will:
 - create a venv in .\env
 - install build requirements
 - generate app.ico
 - run PyInstaller to build a single-file GUI EXE
 - copy the EXE to .\release
 - create a desktop shortcut for the current user
#>

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir
$repoRoot = Resolve-Path ".." | Select-Object -ExpandProperty Path

$venv = Join-Path $scriptDir "env"
if (-Not (Test-Path $venv)) {
    Write-Host "Creating venv at: $venv"
    python -m venv $venv
}
$activate = Join-Path $venv "Scripts\Activate.ps1"

Write-Host "Activating venv and installing build requirements..."
& powershell -NoProfile -ExecutionPolicy Bypass -Command "& '$activate'; python -m pip install --upgrade pip; python -m pip install -r $repoRoot\tools\build-requirements.txt"

# Generate icon
$icon_out = Join-Path $repoRoot "build\app.ico"
Write-Host "Generating icon at: $icon_out"
& powershell -NoProfile -ExecutionPolicy Bypass -Command "& '$activate'; python $repoRoot\tools\generate_icon.py --output $icon_out"

# Build with pyinstaller
$exe_name = 'mdimageembed'
$entry = Join-Path $repoRoot "mdimage_tkui.py"
Write-Host "Running PyInstaller..."
& powershell -NoProfile -ExecutionPolicy Bypass -Command "& '$activate'; pyinstaller --noconfirm --onefile --windowed --icon=$icon_out --name $exe_name $entry"

# Copy exe to release folder
$dist = Join-Path $repoRoot "dist\$exe_name.exe"
$release = Join-Path $repoRoot "release"
if (-Not (Test-Path $release)) { New-Item -ItemType Directory -Path $release | Out-Null }
Copy-Item -Path $dist -Destination $release -Force
Copy-Item -Path $icon_out -Destination $release -Force
Write-Host "Copied EXE and icon to: $release"

# Create desktop shortcut for current user
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop ("$exe_name.lnk")
$s = New-Object -ComObject WScript.Shell
$lnk = $s.CreateShortcut($lnkPath)
$lnk.TargetPath = (Join-Path $release "$exe_name.exe")
$lnk.IconLocation = (Join-Path $release "app.ico")
$lnk.Save()
Write-Host "Created desktop shortcut: $lnkPath"

Write-Host "Build finished. EXE located at: $release\$exe_name.exe"
