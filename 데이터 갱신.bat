@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  출연연 홍보 분석 - 데이터 갱신
echo ========================================
echo.

echo [1/3] 변경 파일 확인 및 스테이징...
git add .
echo.

git diff --cached --quiet
if not errorlevel 1 (
    echo [INFO] 변경된 파일이 없습니다.
    echo        새 엑셀 파일을 이 폴더에 먼저 저장한 뒤 다시 실행하세요.
    echo.
    pause
    exit /b
)

git status --short
echo.

for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd'"') do set TODAY=%%i
for /f "delims=" %%i in ('powershell -NoProfile -Command "$d=Get-Date; $cal=[System.Globalization.CultureInfo]::InvariantCulture.Calendar; $w=$cal.GetWeekOfYear($d, [System.Globalization.CalendarWeekRule]::FirstFourDayWeek, [System.DayOfWeek]::Monday); '{0:D2}' -f $w"') do set WEEK=%%i
for /f "delims=" %%i in ('powershell -NoProfile -Command "(Get-Date).Year"') do set YEAR=%%i

set COMMIT_MSG=data: %YEAR%-W%WEEK% 보도 데이터 갱신 (%TODAY%)

echo [2/3] 커밋 생성: %COMMIT_MSG%
git commit -m "%COMMIT_MSG%"
echo.

echo [3/3] GitHub에 push...
git push
set PUSH_RESULT=%errorlevel%
echo.

if "%PUSH_RESULT%"=="0" (
    echo ========================================
    echo  완료! 1~2분 뒤 Streamlit 대시보드에
    echo  자동으로 새 데이터가 반영됩니다.
    echo ========================================
) else (
    echo ========================================
    echo  [오류] push에 실패했습니다.
    echo  위 빨간 메시지를 확인하거나
    echo  Claude에게 그대로 복사해서 보내세요.
    echo ========================================
)

echo.
pause
