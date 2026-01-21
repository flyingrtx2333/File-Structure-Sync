param(
    [string]$IconPath = ""
)

$iconArg = ""
if ($IconPath -and (Test-Path $IconPath)) {
    $iconArg = "--icon `"$IconPath`""
}

python -m PyInstaller --noconfirm --onefile --windowed --name File-Structure-Sync $iconArg gui.py
