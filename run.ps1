# Starts backend and frontend in two windows and opens the browser.
$root = $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\.venv\Scripts\python.exe manage.py runserver"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"
Start-Sleep -Seconds 8
Start-Process "http://localhost:5173"
