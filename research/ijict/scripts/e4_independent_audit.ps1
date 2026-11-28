param([string]$Repo = (Get-Location).Path, [string]$OutputRoot = (Join-Path $env:TEMP 'pacman-e4-audit'))
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$release = 'aaf3ca5dde1e70ee2a94b2f3571dd7b251f4bc66'
Push-Location $Repo
try {
    $OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
    New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
    $run = Join-Path $OutputRoot ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    $cliDir = Join-Path $run 'independent-cli'
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $node = (Get-Command node -ErrorAction Stop).Source
    $eslint = (Resolve-Path 'node_modules/eslint/bin/eslint.js').Path
    $tsVersion = & $node -p "require('typescript').version"
    if ($LASTEXITCODE -ne 0 -or $tsVersion -ne '5.8.3') { throw 'TypeScript version mismatch' }
    $eslintVersion = & $node $eslint --version
    if ($LASTEXITCODE -ne 0 -or $eslintVersion -ne 'v9.39.1') { throw 'ESLint version mismatch' }
    if (!(Test-Path package-lock.json)) { throw 'Missing package-lock.json' }
    $archive = Get-Content metrics/code-v1.0-final-ci.json -Raw | ConvertFrom-Json
    $files = @(Get-ChildItem versions/*.html)
    if ($files.Count -ne 12 -or @($archive.results).Count -ne 12) { throw 'Unexpected corpus size' }
    $releaseFiles = @(& git ls-tree -r --name-only $release versions | Where-Object { $_ -match '\.html$' })
    if ($LASTEXITCODE -ne 0 -or $releaseFiles.Count -ne 12) { throw 'Unexpected release inventory' }
    if (@(Compare-Object ($files | ForEach-Object { 'versions/' + $_.Name }) $releaseFiles).Count) { throw 'Release inventory mismatch' }
    $basic = @(foreach ($a in $archive.results) {
        $relative = 'versions/' + $a.file
        $blob = & git hash-object $relative
        if ($LASTEXITCODE -ne 0) { throw 'git hash-object failed' }
        $expected = & git rev-parse "${release}:$relative"
        if ($LASTEXITCODE -ne 0 -or $blob -ne $expected) { throw "Frozen source mismatch: $relative" }
        $html = [IO.File]::ReadAllText((Resolve-Path $relative).Path)
        $scripts = [regex]::Matches($html,'(?is)<script\b[^>]*>(.*?)</script>')
        if ($scripts.Count -ne 1) { throw "Unexpected script count: $relative" }
        $js = $scripts[0].Groups[1].Value.Trim()
        $h = ($html.TrimEnd() -split '\r?\n').Count
        $j = ($js -split '\r?\n').Count
        $n = @($js -split '\r?\n' | Where-Object { $_.Trim() -ne '' }).Count
        if ($h -ne $a.htmlLines -or $j -ne $a.jsLines -or $n -ne $a.jsNonblankLines) { throw "Line metrics mismatch: $relative" }
        [pscustomobject]@{Version=$a.file;GitBlob=$blob;SHA256=(Get-FileHash $relative -Algorithm SHA256).Hash.ToLowerInvariant();ScriptBlocks=1;HTML=$h;JS=$j;Nonblank=$n;Match=$true}
    })
    & $node research/ijict/scripts/e4_analyze.cjs $run > "$run.stdout.log" 2> "$run.stderr.log"
    if ($LASTEXITCODE -ne 0) { throw "E4 failed; see $run.stderr.log" }
    New-Item -ItemType Directory -Path $cliDir | Out-Null
    $basic | Export-Csv (Join-Path $run 'source-verification.csv') -NoTypeInformation -Encoding UTF8
    $e4 = Get-Content (Join-Path $run 'results.json') -Raw | ConvertFrom-Json
    $rows = Import-Csv (Join-Path $run 'complexity.csv')
    # Read-only CLI; use UTF-8 temporary files instead of PowerShell stdin encoding.
    $scratch = Join-Path $OutputRoot ('scratch-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $scratch | Out-Null
    try {
        # Use actual files, not node -e or JSON command-line arguments, for Windows PowerShell 5.1.
        $runner = Join-Path $scratch 'runner.cjs'
        $config = Join-Path $scratch 'eslint.config.cjs'
        $runnerSource = @'
const fs = require('node:fs');
const cp = require('node:child_process');
const [input, output, eslint, config] = process.argv.slice(2);
const r = cp.spawnSync(process.execPath, [eslint, '--stdin', '--stdin-filename', 'game-inline.js', '--no-config-lookup', '--config', config, '--no-inline-config', '--format', 'json'], {input: fs.readFileSync(input), maxBuffer: 16777216});
if (r.error) throw r.error;
if (r.stderr) process.stderr.write(r.stderr);
if (r.status !== 0) process.exit(r.status === null ? 1 : r.status);
fs.writeFileSync(output, r.stdout);
'@
        [IO.File]::WriteAllText($runner, $runnerSource, $utf8)
        $configSource = @'
module.exports = [{languageOptions: {ecmaVersion: 2022, sourceType: 'script'}, linterOptions: {noInlineConfig: true, reportUnusedDisableDirectives: 'off'}, rules: {complexity: ['warn', {max: 0, variant: 'classic'}]}}];
'@
        [IO.File]::WriteAllText($config, $configSource, $utf8)
        $comparison = @(foreach ($v in $e4.versions) {
            $html = [IO.File]::ReadAllText((Resolve-Path ('versions/' + $v.file)).Path)
            $js = [regex]::Match($html,'(?is)<script\b[^>]*>(.*?)</script>').Groups[1].Value.Trim()
            $temp = Join-Path $scratch 'game-inline.js'
            [IO.File]::WriteAllText($temp,$js,$utf8)
            $reportPath = Join-Path $cliDir ($v.file + '.json')
            & $node $runner $temp $reportPath $eslint $config
            if ($LASTEXITCODE -ne 0) { throw "CLI failed: $($v.file)" }
            $raw = [IO.File]::ReadAllText($reportPath, $utf8)
            $report = @($raw | ConvertFrom-Json)[0]
            $messages = @($report.messages | Where-Object { $_.ruleId -eq 'complexity' })
            $expected = @($rows | Where-Object { $_.file -eq $v.file })
            $cli = @(foreach ($m in $messages) { if ($m.message -notmatch 'complexity of (\d+)') { throw 'Unexpected CLI message' }; [int]$Matches[1] })
            $cliPos = @(foreach ($m in $messages) { if ($m.message -notmatch 'complexity of (\d+)') { throw 'Unexpected CLI message' }; "$($m.line):$($Matches[1])" })
            $e4Values = @($expected | ForEach-Object { [int]$_.complexity })
            $e4Pos = @($expected | ForEach-Object { "$($_.line):$($_.complexity)" })
            $countMatch = $cli.Count -eq $e4Values.Count
            $cliSum = ($cli | Measure-Object -Sum).Sum
            $e4Sum = ($e4Values | Measure-Object -Sum).Sum
            $dist = (($cli | Sort-Object) -join ',') -eq (($e4Values | Sort-Object) -join ',')
            $pos = (($cliPos | Sort-Object) -join ',') -eq (($e4Pos | Sort-Object) -join ',')
            [pscustomobject]@{Version=$v.file;CLIUnits=$cli.Count;E4Units=$e4Values.Count;CLISum=$cliSum;E4Sum=$e4Sum;Errors=$report.errorCount;FatalErrors=$report.fatalErrorCount;CountMatch=$countMatch;SumMatch=($cliSum -eq $e4Sum);DistributionMatch=$dist;LineComplexityMatch=$pos}
        })
    } finally { Remove-Item -LiteralPath $scratch -Recurse -Force }
    $comparison | Export-Csv (Join-Path $cliDir 'comparison.csv') -NoTypeInformation -Encoding UTF8
    $comparison | Select-Object Version, @{Name='Units';Expression={$_.CLIUnits}}, LineComplexityMatch | Export-Csv (Join-Path $cliDir 'positional-comparison.csv') -NoTypeInformation -Encoding UTF8
    $comparison | Format-Table -AutoSize
    $failed = @($comparison | Where-Object { !$_.CountMatch -or !$_.SumMatch -or !$_.DistributionMatch -or !$_.LineComplexityMatch -or $_.Errors -ne 0 -or $_.FatalErrors -ne 0 })
    if ($failed.Count -ne 0) { throw 'Independent comparison failed' }
    Copy-Item "$run.stdout.log" (Join-Path $run 'run.log')
    Copy-Item "$run.stderr.log" (Join-Path $run 'errors.log')
    Write-Host "PASS: $run"
} finally { Pop-Location }
