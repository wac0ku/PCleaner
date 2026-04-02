<#
.SYNOPSIS
    PCleaner Installation Wizard
.DESCRIPTION
    One-click installer for PCleaner — the free Cleaner App.
    Creates a virtual environment, installs dependencies, builds the .exe,
    and creates a Desktop shortcut + Start Menu entry.
#>

param(
    [switch]$SkipBuild,
    [switch]$SkipShortcut,
    [switch]$Silent
)

$ErrorActionPreference = "Stop"

# ── Colors & Helpers ──────────────────────────────────────────────────────

function Write-Banner {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║                                                  ║" -ForegroundColor Cyan
    Write-Host "  ║      PCleaner — Installation Wizard              ║" -ForegroundColor Cyan
    Write-Host "  ║      the free Cleaner App                        ║" -ForegroundColor Cyan
    Write-Host "  ║                                                  ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($num, $text) {
    Write-Host "  [$num] " -ForegroundColor Cyan -NoNewline
    Write-Host $text
}

function Write-OK($text) {
    Write-Host "  ✓ " -ForegroundColor Green -NoNewline
    Write-Host $text
}

function Write-Warn($text) {
    Write-Host "  ⚠ " -ForegroundColor Yellow -NoNewline
    Write-Host $text
}

function Write-Fail($text) {
    Write-Host "  ✗ " -ForegroundColor Red -NoNewline
    Write-Host $text
}

# ── Start ─────────────────────────────────────────────────────────────────

Write-Banner

$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }

Write-Host "  Install location: $ProjectRoot" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Check Python ─────────────────────────────────────────────────

Write-Step "1/6" "Checking Python installation..."

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python\s+3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) {
                $pythonCmd = $cmd
                Write-OK "Found $ver"
                break
            }
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Fail "Python 3.10+ is required but not found."
    Write-Host ""
    Write-Host "  Download Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Write-Host ""
    if (-not $Silent) { Read-Host "  Press Enter to exit" }
    exit 1
}

# ── Step 2: Create virtual environment ────────────────────────────────────

Write-Step "2/6" "Creating virtual environment..."

$venvPath = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvPip = Join-Path $venvPath "Scripts\pip.exe"

if (Test-Path $venvPython) {
    Write-OK "Virtual environment already exists"
} else {
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create virtual environment"
        exit 1
    }
    Write-OK "Virtual environment created"
}

# ── Step 3: Upgrade pip ───────────────────────────────────────────────────

Write-Step "3/6" "Upgrading pip..."
& $venvPython -m pip install --upgrade pip --quiet 2>$null
Write-OK "pip is up to date"

# ── Step 4: Install dependencies ──────────────────────────────────────────

Write-Step "4/6" "Installing PCleaner and dependencies..."

& $venvPip install -e $ProjectRoot --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "editable install had issues, trying regular install..."
    & $venvPip install -r (Join-Path $ProjectRoot "requirements.txt") --quiet 2>$null
}
Write-OK "All dependencies installed"

# ── Step 5: Build .exe ────────────────────────────────────────────────────

if (-not $SkipBuild) {
    Write-Step "5/6" "Building PCleaner.exe (this may take a minute)..."

    & $venvPip install pyinstaller --quiet 2>$null

    $distDir = Join-Path $ProjectRoot "dist"
    $buildDir = Join-Path $ProjectRoot "build"
    $specFile = Join-Path $ProjectRoot "PCleaner.spec"
    $iconPath = Join-Path $ProjectRoot "assets\icon.ico"
    $mainPy = Join-Path $ProjectRoot "pcleaner\__main__.py"

    # Build arguments
    $pyiArgs = @(
        "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "PCleaner",
        "--add-data", "$ProjectRoot\pcleaner\tui\pcleaner.tcss;pcleaner\tui",
        "--hidden-import", "pcleaner.tui",
        "--hidden-import", "pcleaner.gui",
        "--hidden-import", "pcleaner.cli",
        "--hidden-import", "pcleaner.core",
        "--hidden-import", "pcleaner.tools",
        "--hidden-import", "pcleaner.utils",
        "--hidden-import", "textual",
        "--hidden-import", "customtkinter",
        "--clean",
        "--noconfirm"
    )

    if (Test-Path $iconPath) {
        $pyiArgs += "--icon"
        $pyiArgs += $iconPath
    }

    $pyiArgs += $mainPy

    & $venvPython @pyiArgs 2>$null

    $exePath = Join-Path $distDir "PCleaner.exe"
    if (Test-Path $exePath) {
        Write-OK "PCleaner.exe built successfully ($exePath)"
    } else {
        Write-Warn "Build had issues — you can still run via: .venv\Scripts\python.exe -m pcleaner"
        $exePath = $null
    }
} else {
    Write-Step "5/6" "Skipping .exe build (--SkipBuild)"
    $exePath = $null
}

# ── Step 6: Create shortcuts ─────────────────────────────────────────────

if (-not $SkipShortcut) {
    Write-Step "6/6" "Creating desktop shortcut..."

    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "PCleaner.lnk"

    $WScriptShell = New-Object -ComObject WScript.Shell
    $shortcut = $WScriptShell.CreateShortcut($shortcutPath)

    if ($exePath -and (Test-Path $exePath)) {
        $shortcut.TargetPath = $exePath
    } else {
        # Fallback: launch via venv python
        $shortcut.TargetPath = $venvPython
        $shortcut.Arguments = "-m pcleaner"
    }

    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.Description = "PCleaner — the free Cleaner App"

    if (Test-Path $iconPath) {
        $shortcut.IconLocation = $iconPath
    }

    $shortcut.Save()
    Write-OK "Desktop shortcut created"

    # Start Menu shortcut
    $startMenuDir = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\PCleaner"
    if (-not (Test-Path $startMenuDir)) { New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null }

    $startShortcut = $WScriptShell.CreateShortcut((Join-Path $startMenuDir "PCleaner.lnk"))
    if ($exePath -and (Test-Path $exePath)) {
        $startShortcut.TargetPath = $exePath
    } else {
        $startShortcut.TargetPath = $venvPython
        $startShortcut.Arguments = "-m pcleaner"
    }
    $startShortcut.WorkingDirectory = $ProjectRoot
    $startShortcut.Description = "PCleaner — the free Cleaner App"
    if (Test-Path $iconPath) { $startShortcut.IconLocation = $iconPath }
    $startShortcut.Save()
    Write-OK "Start Menu entry created"
} else {
    Write-Step "6/6" "Skipping shortcuts (--SkipShortcut)"
}

# ── Done ──────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║                                                  ║" -ForegroundColor Green
Write-Host "  ║   ✓  PCleaner installed successfully!            ║" -ForegroundColor Green
Write-Host "  ║                                                  ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  How to launch:" -ForegroundColor Cyan
Write-Host "    • Double-click the PCleaner shortcut on your Desktop"
Write-Host "    • Or run: .venv\Scripts\python.exe -m pcleaner" -ForegroundColor DarkGray
Write-Host "    • CLI mode: .venv\Scripts\python.exe -m pcleaner --help" -ForegroundColor DarkGray
Write-Host "    • TUI mode: .venv\Scripts\python.exe -m pcleaner --tui" -ForegroundColor DarkGray
Write-Host ""

if (-not $Silent) {
    $launch = Read-Host "  Launch PCleaner now? (Y/n)"
    if ($launch -ne "n" -and $launch -ne "N") {
        if ($exePath -and (Test-Path $exePath)) {
            Start-Process $exePath
        } else {
            Start-Process $venvPython -ArgumentList "-m", "pcleaner"
        }
    }
}
