# ==============================================================================
# BotMAX Studio — Android APK Automated Builder
# ==============================================================================
param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $PSScriptRoot
$androidDir = Join-Path $rootDir "android"
$manifestPath = Join-Path $androidDir "app\src\main\AndroidManifest.xml"

# Read existing version from AndroidManifest.xml
[xml]$manifestXml = Get-Content $manifestPath
$currentCode = [int]$manifestXml.manifest.versionCode
$currentName = $manifestXml.manifest.versionName

if (-not $Version) {
    # Auto-increment patch version (e.g. 1.0.0 -> 1.0.1)
    $parts = $currentName.Split('.')
    if ($parts.Length -eq 3) {
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        $patch = [int]$parts[2] + 1
        $Version = "$major.$minor.$patch"
    } else {
        $Version = "$currentName.1"
    }
}

$newCode = $currentCode + 1

# Update AndroidManifest.xml with new version
$manifestContent = Get-Content $manifestPath -Raw
$manifestContent = [regex]::Replace($manifestContent, 'android:versionCode="\d+"', "android:versionCode=`"$newCode`"")
$manifestContent = [regex]::Replace($manifestContent, 'android:versionName="[^"]+"', "android:versionName=`"$Version`"")
Set-Content -Path $manifestPath -Value $manifestContent -Encoding UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 🎰 BotMAX Admin APK Builder v$Version (Build #$newCode)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$buildDir = Join-Path $androidDir "build"
$sdkDir = "C:\Users\user1\android-sdk"
$jbrDir = "C:\Program Files\GIGA IDE\GIGA IDE CE 2025.1\jbr"

# Tools
$javac = Join-Path $jbrDir "bin\javac.exe"
$keytool = Join-Path $jbrDir "bin\keytool.exe"
$aapt2 = Join-Path $sdkDir "build-tools\34.0.0\aapt2.exe"
$d8 = Join-Path $sdkDir "build-tools\34.0.0\d8.bat"
$zipalign = Join-Path $sdkDir "build-tools\34.0.0\zipalign.exe"
$apksigner = Join-Path $sdkDir "build-tools\34.0.0\apksigner.bat"
$androidJar = Join-Path $sdkDir "platforms\android-34\android.jar"

$env:JAVA_HOME = $jbrDir
$env:PATH = "$jbrDir\bin;$env:PATH"

# Prepare build dirs
if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
New-Item -ItemType Directory -Path "$buildDir\gen" -Force | Out-Null
New-Item -ItemType Directory -Path "$buildDir\classes" -Force | Out-Null
New-Item -ItemType Directory -Path "$buildDir\dex" -Force | Out-Null

Write-Host "1. Compiling Android resources with aapt2..." -ForegroundColor Yellow
& $aapt2 compile --dir (Join-Path $androidDir "app\src\main\res") -o "$buildDir\res.zip"

Write-Host "2. Linking resources and generating R.java..." -ForegroundColor Yellow
& $aapt2 link -I $androidJar "$buildDir\res.zip" --manifest $manifestPath -o "$buildDir\unaligned.apk" --java "$buildDir\gen"

Write-Host "3. Compiling Java sources with javac..." -ForegroundColor Yellow
$javaSources = Get-ChildItem -Recurse (Join-Path $androidDir "app\src\main\java") -Filter *.java | Select-Object -ExpandProperty FullName
$rJava = Join-Path $buildDir "gen\ru\botmax\admin\R.java"
& $javac -g:none --release 11 -encoding UTF-8 -cp $androidJar -d "$buildDir\classes" $rJava $javaSources

Write-Host "4. Compiling Dalvik bytecode (DEX) with d8..." -ForegroundColor Yellow
$classFiles = Get-ChildItem -Recurse "$buildDir\classes" -Filter *.class | Select-Object -ExpandProperty FullName
& $d8 --min-api 24 --lib $androidJar --output "$buildDir\dex" $classFiles

Write-Host "5. Packaging classes.dex into APK..." -ForegroundColor Yellow
$pyUnaligned = "$buildDir\unaligned.apk".Replace('\', '/')
$pyDex = "$buildDir\dex\classes.dex".Replace('\', '/')
python -c "
import zipfile
with zipfile.ZipFile('$pyUnaligned', 'a', compression=zipfile.ZIP_DEFLATED) as z:
    z.write('$pyDex', 'classes.dex')
"

Write-Host "6. Aligning APK with zipalign..." -ForegroundColor Yellow
$alignedApk = "$buildDir\botmax-admin-aligned.apk"
& $zipalign -p -f 4 "$buildDir\unaligned.apk" $alignedApk

Write-Host "7. Signing APK with apksigner..." -ForegroundColor Yellow
$keystore = Join-Path $androidDir "botmax-release.keystore"
if (-not (Test-Path $keystore)) {
    & $keytool -genkeypair -v -keystore $keystore -storepass "botmax2026" -alias "botmax" -keypass "botmax2026" -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=BotMAX Admin, OU=Admin, O=BotMAX, L=Moscow, C=RU"
}

$outputApk = Join-Path $rootDir "botmax-admin-v$Version.apk"
$staticApk = Join-Path $rootDir "botmax\src\static\botmax-admin.apk"

& $apksigner sign --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true --ks $keystore --ks-key-alias "botmax" --ks-pass "pass:botmax2026" --key-pass "pass:botmax2026" --out $outputApk $alignedApk

Copy-Item $outputApk $staticApk -Force

# Write version metadata for web client & admin
$versionJsonPath = Join-Path $rootDir "botmax\src\static\version.json"
$verMeta = [PSCustomObject]@{
    version = $Version
    versionCode = $newCode
    built_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
}
$verMeta | ConvertTo-Json | Out-File -FilePath $versionJsonPath -Encoding utf8

Write-Host "========================================"
Write-Host " APK BUILD SUCCESS!"
Write-Host " File: $outputApk"
Write-Host " Version: v$Version (Build #$newCode)"
Write-Host " Download URL: /apk"
Write-Host "========================================"
