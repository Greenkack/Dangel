Write-Host "`nStarte automatische Problembehebung für pandas..." -ForegroundColor Cyan

# Projektverzeichnis
$projectPath = "C:\SolarDING_App"

# Schritt 1: Prüfe auf störende pandas.py Datei
$pandasFakePath = Join-Path $projectPath "pandas.py"
if (Test-Path $pandasFakePath) {
    Write-Host "WARNUNG: Datei $pandasFakePath existiert und kann pandas stören." -ForegroundColor Yellow
    Rename-Item $pandasFakePath -NewName "pandas_backup.py"
    Write-Host "Umbenannt zu pandas_backup.py"
}

# Schritt 2: __pycache__ Ordner löschen
$cacheFolders = @(
    "$projectPath\__pycache__",
    "$env:LOCALAPPDATA\Programs\Python\Python313\Lib\site-packages\pandas\__pycache__"
)
foreach ($folder in $cacheFolders) {
    if (Test-Path $folder) {
        Remove-Item -Recurse -Force $folder
        Write-Host "Gelöscht: $folder" -ForegroundColor Green
    }
}

# Schritt 3: pandas deinstallieren und korrekt installieren
Write-Host "Deinstalliere pandas..." -ForegroundColor DarkCyan
pip uninstall -y pandas

Write-Host "Installiere pandas Version 2.2.2..." -ForegroundColor DarkCyan
pip install pandas==2.2.2 --no-cache-dir

# Schritt 4: Test ob pandas funktioniert
Write-Host "Teste pandas..."
python -c "import pandas as pd; print('pandas Version:', pd.__version__)"

Write-Host "Alles abgeschlossen! Starte deine App neu." -ForegroundColor Green
