@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    python -m streamlit run app\main.py
) else (
    echo No se encontro el entorno virtual en .venv.
    echo Crea el entorno con: py -3.14 -m venv .venv
    echo Luego instala dependencias con: python -m pip install -r requirements.txt
)

endlocal
