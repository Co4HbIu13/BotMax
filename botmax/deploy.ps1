# Automated Deployment Script for BotMAX
$PythonPath = ".\venv\Scripts\python.exe"

if (Test-Path $PythonPath) {
    & $PythonPath deploy_now.py
} else {
    python deploy_now.py
}
