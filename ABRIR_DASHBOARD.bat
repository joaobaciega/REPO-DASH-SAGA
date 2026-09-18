@echo off
cd /d "%~dp0"
echo Acesse http://localhost:8503 no navegador.
python -m streamlit run app.py --server.port 8503
pause
