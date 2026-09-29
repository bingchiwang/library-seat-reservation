@echo off
echo Starting Library Seat Reservation System...
echo.
echo After the server starts, open your browser and go to http://127.0.0.1:8000
echo Press Ctrl+C in this window to stop the server.
echo.

:: Try uvicorn directly
uvicorn main:app --reload

:: If that fails, try python -m
python -m uvicorn main:app --reload

:: If that fails, try py -m
py -m uvicorn main:app --reload

echo.
echo Server stopped or an error occurred.
pause
