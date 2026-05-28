@echo off
chcp 65001 >nul
cd /d "%~dp0.."
setlocal enabledelayedexpansion

:: ============================================================
::  RPGTL 前端构建脚本
::  把 UniApp H5 产物同步到 Android assets/mobile_ui
:: ============================================================

echo ============================================================
echo   RPGTL 前端 → Android assets 同步脚本
echo ============================================================
echo.

set APP_DIR=AndroidAPP\AndroidAPP
set OUT_DIR=%APP_DIR%\unpackage\dist\build\h5
set TARGET=android_app\shell\app\src\main\assets\mobile_ui

:: ---- 1. 检查是否有 HBuilderX 可执行 ----
set HBX=
for %%p in (
    "D:\HBuilderX\HBuilderX.exe"
    "C:\Program Files\HBuilderX\HBuilderX.exe"
) do (
    if exist %%p set HBX=%%p
)

if not "%HBX%"=="" (
    echo [方式 A] 用 HBuilderX GUI 构建
    echo.
    echo   请执行以下操作：
    echo   1. 用 HBuilderX 打开 %CD%\%APP_DIR%
    echo   2. 菜单 → 发行 → 网站-PC Web或手机H5
    echo   3. 等待构建完成
    echo.
    start "" %HBX% "%CD%\%APP_DIR%"
    echo   已启动 HBuilderX ...
    echo   构建完成后按任意键继续复制文件
    pause >nul
) else (
    echo [方式 B] 未找到 HBuilderX，尝试用 CLI 构建...
    echo.
    set HBX_CLI=D:\HBuilderX\cli.exe
    if not exist "!HBX_CLI!" (
        echo   ❌ 未找到 HBuilderX CLI (D:\HBuilderX\cli.exe)
        echo   ❌ 无法自动构建 UniApp H5
        echo.
        echo   请手动在 HBuilderX 中：
        echo   1. 打开 %CD%\%APP_DIR%
        echo   2. 发行 → 网站-PC Web或手机H5
        echo   3. 把输出目录内容复制到 %TARGET%
        echo.
        goto :check_manual
    )
    
    "!HBX_CLI!" publish --platform h5 --project "%CD%\%APP_DIR%"
    if errorlevel 1 (
        echo   ❌ CLI 构建失败
        goto :check_manual
    )
)

:: ---- 2. 查找构建产物 ----
:find_output
echo.
echo 正在查找构建产物 ...

set FOUND=
for %%d in (
    "%OUT_DIR%"
    "%APP_DIR%\dist\build\h5"
    "%APP_DIR%\dist\build\web"
    "%APP_DIR%\unpackage\dist\build\web"
) do (
    if exist "%%d\index.html" if exist "%%d\assets\" (
        set FOUND=%%d
        echo ✅ 找到: %%d
    )
)

if "%FOUND%"=="" (
    :: try to find any h5 dir
    for /f "delims=" %%d in ('dir /s /b /ad "%APP_DIR%\unpackage" 2^>nul ^| findstr "\\h5$ \\web$" 2^>nul') do (
        if exist "%%d\index.html" (
            set FOUND=%%d
            echo ✅ 找到: %%d
        )
    )
)

if "%FOUND%"=="" goto :check_manual

:: ---- 3. 验证产物 ----
echo.
echo 验证构建产物 ...

set VALID=0
for %%f in ("%FOUND%\index.html") do set /a VALID+=1
for %%f in ("%FOUND%\assets\*.js") do set /a VALID+=1

if %VALID% lss 2 (
    echo ❌ 构建产物不完整 index.html 或 assets/*.js 缺失
    goto :check_manual
)

echo ✅ 验证通过

:: ---- 4. 复制到 Android assets ----
echo.
echo 同步到 %TARGET% ...

if exist "%TARGET%\index.html" (
    :: 备份现有版本
    for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set ts=%%i
    set BACKUP=%TARGET%_backup_!ts:~0,14!
    xcopy /E /I /Y "%TARGET%" "!BACKUP!" >nul
    echo   旧版本已备份到 mobile_ui_backup_!ts:~0,14!
)

:: 清理旧文件
if exist "%TARGET%" rmdir /S /Q "%TARGET%"

:: 复制新文件
xcopy /E /I /Y "%FOUND%\*" "%TARGET%" >nul

echo ✅ 前端已同步到 Android assets

:: ---- 5. 验证目标 ----
echo.
echo 最终验证 ...

for %%f in ("%TARGET%\index.html") do echo   ✅ index.html 存在
for %%f in ("%TARGET%\assets\*.js") do echo   ✅ JS bundle 存在

echo.
echo ============================================================
echo   同步完成！可以运行 Gradle 打包了
echo ============================================================
goto :end

:check_manual
echo.
echo ============================================================
echo   自动同步失败，请手动操作：
echo.
echo   1. 在 HBuilderX 中发行 UniApp 为 H5
echo   2. 找到输出目录（含 index.html + assets/）
echo   3. 复制到:
echo      %CD%\%TARGET%
echo   4. 运行 Gradle 打包
echo ============================================================

:end
endlocal
pause
