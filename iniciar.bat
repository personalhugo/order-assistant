@echo off
rem Abre a API (FastAPI) e a tela (Streamlit) em duas janelas. Feche as janelas para parar.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente .venv nao encontrado nesta pasta.
  echo Crie com:  python -m venv .venv
  echo Depois:    .venv\Scripts\python -m pip install -r requirements-dev.txt
  pause
  exit /b 1
)

start "API - Assistente de Pedidos" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload"
start "Tela - Assistente de Pedidos" cmd /k ".venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py"

echo Abrindo a API (http://localhost:8000/docs) e a tela (http://localhost:8501)...
echo Para parar, feche as duas janelas que abriram.
ping -n 4 127.0.0.1 >nul
