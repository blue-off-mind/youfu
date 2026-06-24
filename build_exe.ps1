$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$AppName = [string]([char]0x5E7D) + [string]([char]0x6D6E)
$MojibakeAppName = [string]([char]0x9A9E) + [string]([char]0x82A5) + [string]([char]0x8BDE)
$LegacyAppNames = @("TTS-Orb", $MojibakeAppName)

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
python -c "import PyInstaller" *> $null
$HasPyInstaller = $LASTEXITCODE -eq 0
$ErrorActionPreference = $PreviousErrorActionPreference

if (-not $HasPyInstaller) {
    python -m pip install pyinstaller
}

$ProcessNames = @("$AppName.exe") + ($LegacyAppNames | ForEach-Object { "$_.exe" })
$ExistingProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in $ProcessNames -and $_.ExecutablePath -like "$Root*"
}
foreach ($Process in $ExistingProcesses) {
    Stop-Process -Id $Process.ProcessId -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $AppName `
    --collect-all sounddevice `
    --collect-all soundcard `
    --collect-submodules pynput `
    --hidden-import voice_turn `
    --hidden-import gemini_brain `
    --hidden-import tts `
    .\desktop_orb.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$DistRoot = Join-Path $Root "dist"
$BuildRoot = Join-Path $Root "build"
$AppDir = Join-Path $DistRoot $AppName
$ReleaseRoot = Join-Path $Root "release"
$ReleaseDir = Join-Path $ReleaseRoot $AppName

Copy-Item -Path (Join-Path $Root "gemini_config.json") -Destination $AppDir -Force
Copy-Item -Path (Join-Path $Root "tts_config.json") -Destination $AppDir -Force
Copy-Item -Path (Join-Path $Root "session_config.json") -Destination $AppDir -Force
Copy-Item -Path (Join-Path $Root "desktop_config.json") -Destination $AppDir -Force
Copy-Item -Path (Join-Path $Root "inspect_diagnostics.py") -Destination $AppDir -Force
foreach ($Name in @("prompts", "skins", "assets")) {
    $SourceDir = Join-Path $Root $Name
    if (Test-Path -LiteralPath $SourceDir) {
        Copy-Item -Path $SourceDir -Destination $AppDir -Recurse -Force
    }
}

$PrivateLocalReleasePaths = @(
    "assets\skins\user-face",
    "skins\user-face.json"
)
foreach ($RelativePath in $PrivateLocalReleasePaths) {
    $PrivatePath = Join-Path $AppDir $RelativePath
    if (Test-Path -LiteralPath $PrivatePath) {
        Remove-Item -LiteralPath $PrivatePath -Recurse -Force
    }
}

foreach ($Name in @("outputs", "sessions", "tmp")) {
    New-Item -ItemType Directory -Path (Join-Path $AppDir $Name) -Force | Out-Null
}

$ResolvedReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
function Remove-ChildDirectoryUnder {
    param(
        [string] $Parent,
        [string] $Child
    )
    $ResolvedParent = [System.IO.Path]::GetFullPath($Parent)
    $ResolvedChild = [System.IO.Path]::GetFullPath($Child)
    if (-not $ResolvedChild.StartsWith($ResolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean unexpected path: $ResolvedChild"
    }
    if (Test-Path -LiteralPath $Child) {
        Remove-Item -LiteralPath $Child -Recurse -Force
    }
}

Remove-ChildDirectoryUnder -Parent $ReleaseRoot -Child $ReleaseDir
foreach ($LegacyName in $LegacyAppNames) {
    Remove-ChildDirectoryUnder -Parent $ReleaseRoot -Child (Join-Path $ReleaseRoot $LegacyName)
}
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
Copy-Item -Path $AppDir -Destination $ReleaseRoot -Recurse -Force
foreach ($LegacyName in $LegacyAppNames) {
    Remove-ChildDirectoryUnder -Parent $DistRoot -Child (Join-Path $DistRoot $LegacyName)
    Remove-ChildDirectoryUnder -Parent $BuildRoot -Child (Join-Path $BuildRoot $LegacyName)
    $LegacySpec = Join-Path $Root "$LegacyName.spec"
    if (Test-Path -LiteralPath $LegacySpec) {
        Remove-Item -LiteralPath $LegacySpec -Force
    }
}

$BuildExe = Join-Path $Root "build\$AppName\$AppName.exe"
$BuildShortcut = Join-Path $Root "build\$AppName\$AppName.exe - 快捷方式.lnk"
foreach ($Path in @($BuildExe, $BuildShortcut)) {
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

Write-Host "Built runnable app: $ReleaseDir\$AppName.exe"
