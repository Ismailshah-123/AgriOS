# Runs the backend suite against the isolated throwaway test cluster (port 54329).
# Never uses DATABASE_URL. Extra pytest arguments are passed through.
. "$PSScriptRoot\common.ps1"
Push-Location $Backend
try {
    & uv run python scripts/test_db.py start | Out-Null
    $env:TEST_DATABASE_URL = (& uv run python scripts/test_db.py url).Trim()
    & uv run pytest -W error @args
    exit $LASTEXITCODE
} finally {
    Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}
