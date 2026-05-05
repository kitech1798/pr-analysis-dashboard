@echo off
chcp 949 > nul
cd /d "%~dp0"
echo.
echo ========================================
echo  출연연 홍보 분석 대시보드 시작
echo ========================================
echo.
echo 브라우저가 자동으로 열립니다...
echo 종료하려면 이 창을 닫으세요.
echo.
streamlit run app.py --server.headless=false --browser.gatherUsageStats=false
pause