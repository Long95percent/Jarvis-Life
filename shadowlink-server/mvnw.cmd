@echo off
setlocal

set "WRAPPER_PROPERTIES=%~dp0.mvn\wrapper\maven-wrapper.properties"
if not exist "%WRAPPER_PROPERTIES%" (
    echo Error: .mvn\wrapper\maven-wrapper.properties not found >&2
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%a in ("%WRAPPER_PROPERTIES%") do (
    if "%%a"=="distributionUrl" set "DIST_URL=%%b"
)

set "WRAPPER_DIR=%~dp0.mvn\wrapper"
set "MAVEN_HOME=%WRAPPER_DIR%\maven"
set "MAVEN_BIN=%MAVEN_HOME%\bin\mvn.cmd"

if not exist "%MAVEN_BIN%" (
    echo Downloading Maven from: %DIST_URL%
    mkdir "%WRAPPER_DIR%\tmp" 2>nul
    set "ARCHIVE=%WRAPPER_DIR%\tmp\maven.zip"
    powershell -Command "Invoke-WebRequest -Uri '%DIST_URL%' -OutFile '%WRAPPER_DIR%\tmp\maven.zip'"
    powershell -Command "Expand-Archive -Path '%WRAPPER_DIR%\tmp\maven.zip' -DestinationPath '%WRAPPER_DIR%\tmp' -Force"
    for /d %%d in ("%WRAPPER_DIR%\tmp\apache-maven-*") do move "%%d" "%MAVEN_HOME%" >nul
    rmdir /s /q "%WRAPPER_DIR%\tmp" 2>nul
)

"%MAVEN_BIN%" %*

endlocal
