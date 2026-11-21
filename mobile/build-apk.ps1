# Builds the Pathya Android app (a debug APK you can sideload) and copies it to mobile/pathya.apk, which the server
# offers at /pathya.apk (More > Android app). Needs JDK 21 and the Android SDK (platform 36, build-tools 35).
param(
    [string]$Jdk = $(if ($env:JAVA_HOME) { $env:JAVA_HOME } else { (Get-ChildItem C:\dev\tools\jdk -Directory -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }),
    [string]$Sdk = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "C:\dev\tools\android-sdk" })
)
$ErrorActionPreference = "Stop"
if (-not $Jdk -or -not (Test-Path "$Jdk\bin\java.exe")) { throw "JDK 21 not found: pass -Jdk or set JAVA_HOME." }
if (-not (Test-Path "$Sdk\platforms")) { throw "Android SDK not found at ${Sdk}: pass -Sdk or set ANDROID_HOME." }
$env:JAVA_HOME = $Jdk
$env:ANDROID_HOME = $Sdk
$env:Path = "$Jdk\bin;$env:Path"

Push-Location $PSScriptRoot
try {
    if (-not (Test-Path node_modules)) { npm install }
    npx cap sync android
    Set-Content android\local.properties ("sdk.dir=" + ($Sdk -replace '\\', '\\' -replace ':', '\:')) -Encoding ascii
    Push-Location android
    try { .\gradlew.bat assembleDebug } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "Gradle build failed." }
    Copy-Item android\app\build\outputs\apk\debug\app-debug.apk pathya.apk -Force
    "Built mobile\pathya.apk ({0:N1} MB)" -f ((Get-Item pathya.apk).Length / 1MB)
} finally { Pop-Location }
