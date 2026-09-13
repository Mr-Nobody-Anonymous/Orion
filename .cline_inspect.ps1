Set-StrictMode -Off
$root = 'C:\Users\hp\Desktop\Orion'
$out  = Join-Path $root '.cline_state.txt'
$lines = @()

$lines += '=== GIT HEAD ==='
$lines += (git -C $root rev-parse HEAD)
$lines += '=== GIT LOG 3 ==='
$lines += (git -C $root log --oneline -3)
$lines += ('DIRTY_COUNT=' + @(git -C $root status --porcelain).Count)

$lines += '=== ROOT DIRS ==='
$lines += ((Get-ChildItem $root -Force -Directory | Select-Object -ExpandProperty Name) -join ', ')

$lines += '=== KEY PATHS ==='
foreach ($p in @(
  'registry','adapters','third_party','reports','engines','source_repositories',
  'docs/INTEGRATION_MATRIX.md','docs/REPOSITORY_GUIDE.md','docs/RISK_ARCHITECTURE.md',
  'docs/AI_COUNCIL.md','docs/EXECUTION_ARCHITECTURE.md','docs/UI_ARCHITECTURE.md','docs/RESEARCH_ARCHITECTURE.md',
  'tools/license_audit.py','scripts/sync_repositories.py','tools/generate_repo_manifest.py',
  'tests/integration/test_institutional_adapters.py'
)) {
  $lines += ($p + ' => ' + (Test-Path (Join-Path $root $p)))
}

$lines += '=== registry CONTENTS ==='
$reg = Join-Path $root 'registry'
if (Test-Path $reg) {
  $lines += ((Get-ChildItem $reg -Recurse -Name | Select-Object -First 60) -join '; ')
} else { $lines += 'MISSING' }

$lines += '=== reports CONTENTS ==='
$rep = Join-Path $root 'reports'
if (Test-Path $rep) {
  $lines += ((Get-ChildItem $rep -Name | Select-Object -First 40) -join '; ')
} else { $lines += 'MISSING' }

$lines += '=== adapters/ CONTENTS ==='
$ada = Join-Path $root 'adapters'
if (Test-Path $ada) { $lines += ((Get-ChildItem $ada -Recurse -Name | Select-Object -First 60) -join '; ') } else { $lines += 'MISSING' }

$lines += '=== src/orion MODULES ==='
$lines += ((Get-ChildItem (Join-Path $root 'src\orion') -Name) -join ', ')

$lines += '=== source_repositories ==='
$sr = Join-Path $root 'source_repositories'
if (Test-Path $sr) {
  $lines += ((Get-ChildItem $sr -Recurse -Depth 2 -Name | Select-Object -First 40) -join '; ')
} else { $lines += 'MISSING' }

$lines | Out-File -FilePath $out -Encoding utf8
Write-Output ('WROTE ' + $out + ' LINES=' + $lines.Count)
