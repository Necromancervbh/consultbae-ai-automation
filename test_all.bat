@echo off
set PYTHONPATH=.
if exist "C:\Users\EXCEL\python311\python.exe" (
    set PY_EXE=C:\Users\EXCEL\python311\python.exe
) else (
    set PY_EXE=python
)
%PY_EXE% -m unittest tests/test_full_suite.py
pause
