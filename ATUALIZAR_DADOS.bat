@echo off
cd /d "%~dp0"
python atualizar_base.py %*
if errorlevel 1 (
    echo.
    echo A atualizacao apresentou erro. Confira o resultado acima.
) else (
    echo.
    echo Atualizacao concluida nos destinos selecionados.
)
pause
