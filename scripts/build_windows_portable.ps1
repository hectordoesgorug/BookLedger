$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$bundle = Join-Path $repo 'build\windows\BookLedger'
$zip = Join-Path $repo 'dist\BookLedger-portable-candidate.zip'
$apkInput = Join-Path $repo 'release-input\BookLedger-Android.apk'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Build Python not found: $python. Create .venv and install requirements-windows-build.txt first."
}

Push-Location $repo
try {
    & $python -c "import importlib.metadata as m,sys; expected={'Pillow':'12.3.0','ttkbootstrap':'2.2.3','qrcode':'8.2','zeroconf':'0.153.0','ifaddr':'0.2.0','pyinstaller':'6.22.3','pyinstaller-hooks-contrib':'2026.8'}; actual={name:m.version(name) for name in expected}; mismatches={name:(actual[name],target) for name,target in expected.items() if actual[name] != target}; print('Build versions:', sys.version.split()[0], actual); assert sys.version_info[:3] == (3,14,6) and sys.maxsize > 2**32, 'Build requires 64-bit CPython 3.14.6'; assert not mismatches, f'Version mismatch: {mismatches}'"
    if ($LASTEXITCODE -ne 0) { throw 'The active .venv does not match the pinned Windows build requirements.' }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'The build environment has inconsistent dependencies.' }

    & $python -m PyInstaller --noconfirm --clean --distpath (Join-Path $repo 'build\windows') --workpath (Join-Path $repo 'build\windows-work') (Join-Path $repo 'BookLedger.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

    $prepareArgs = @((Join-Path $repo 'scripts\prepare_portable_distribution.py'), $bundle)
    if (Test-Path -LiteralPath $apkInput -PathType Leaf) {
        $sdkRoot = $env:ANDROID_SDK_ROOT
        if (-not $sdkRoot) { $sdkRoot = $env:ANDROID_HOME }
        if (-not $sdkRoot) { $sdkRoot = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
        $buildTools = Join-Path $sdkRoot 'build-tools'
        $apksigner = Get-ChildItem -LiteralPath $buildTools -Directory -ErrorAction SilentlyContinue |
            Sort-Object { [version]$_.Name } -Descending |
            ForEach-Object { Join-Path $_.FullName 'apksigner.bat' } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
        if (-not $apksigner) { throw 'A signed APK was provided, but Android SDK apksigner was not found.' }
        $signatureReport = & $apksigner verify --print-certs $apkInput 2>&1
        if ($LASTEXITCODE -ne 0) { throw "The supplied APK signature did not verify: $signatureReport" }
        if ("$signatureReport" -match 'CN=Android Debug') { throw 'Debug-signed APKs are not accepted in the portable package.' }
        $prepareArgs += @('--apk', $apkInput)
    }
    & $python @prepareArgs
    if ($LASTEXITCODE -ne 0) { throw 'Portable distribution preparation failed.' }

    New-Item -ItemType Directory -Force -Path (Split-Path $zip -Parent) | Out-Null
    Compress-Archive -LiteralPath $bundle -DestinationPath $zip -CompressionLevel Optimal -Force
    Write-Output "Candidate ZIP: $zip"
    if (Test-Path -LiteralPath (Join-Path $bundle 'mobile\BookLedger-Android.apk')) {
        Write-Output 'The candidate includes the verified signed Android APK.'
    }
    else {
        Write-Output 'The candidate omits the Android APK until a signed release artifact is available.'
    }
}
finally {
    Pop-Location
}
