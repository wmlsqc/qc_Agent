param(
    [string]$ServiceName = "agent-project",
    [string]$StreamlitHealthUrl = "http://127.0.0.1:8502/_stcore/health"
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]
$TempScriptDir = Join-Path $PSScriptRoot ".tmp_project_checks"

function Invoke-Check {
    param(
        [string]$Name,
        [scriptblock]$Check
    )

    Write-Host ""
    Write-Host "[CHECK] $Name"
    try {
        & $Check
        Write-Host "[PASS] $Name" -ForegroundColor Green
    }
    catch {
        $message = $_.Exception.Message
        Write-Host "[FAIL] $Name - $message" -ForegroundColor Red
        $script:failures.Add("${Name}: $message")
    }
}

function Assert-LastExitCode {
    param([string]$Message)

    if ($LASTEXITCODE -ne 0) {
        throw "$Message exited with code $LASTEXITCODE"
    }
}

function Invoke-ContainerPythonScript {
    param(
        [string]$Name,
        [string]$Code
    )

    if (-not (Test-Path $TempScriptDir)) {
        New-Item -ItemType Directory -Path $TempScriptDir | Out-Null
    }

    $scriptPath = Join-Path $TempScriptDir $Name
    $containerPath = "scripts/.tmp_project_checks/$Name"
    try {
        Set-Content -Path $scriptPath -Value $Code -Encoding UTF8
        & docker compose exec -T $ServiceName python $containerPath
        Assert-LastExitCode $Name
    }
    finally {
        if (Test-Path $scriptPath) {
            Remove-Item -LiteralPath $scriptPath -Force
        }
    }
}

Write-Host "Running project regression checks with Docker Compose service: $ServiceName"

Invoke-Check "Python key module compilation" {
    $modules = @(
        "app.py",
        "agent/react_agent.py",
        "agent/tools/agent_tools.py",
        "agent/tools/middleware.py",
        "api/main.py",
        "context/context_builder.py",
        "memory/local_memory.py",
        "planning/simple_planner.py",
        "rag/rag_service.py",
        "rag/vector_store.py",
        "services/chat_service.py",
        "services/diagnostics_service.py",
        "utils/csv_handler.py",
        "evaluations/run_basic_checks.py"
    )
    & docker compose exec -T $ServiceName python -m py_compile @modules
    Assert-LastExitCode "py_compile"
}

Invoke-Check "Agent diagnostics" {
    $code = @'
from agent.tools.agent_tools import get_agent_diagnostics

text = get_agent_diagnostics.invoke({})
required = ["qwen3-max", "text-embedding-v4", "data/external/users.csv", "DASHSCOPE_API_KEY"]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("missing diagnostics fields: " + ", ".join(missing))
if "sk-" in text or "DASHSCOPE_API_KEY=" in text:
    raise SystemExit("secret-like content detected")
print("diagnostics_ok")
'@
    Invoke-ContainerPythonScript "agent_diagnostics_check.py" $code
}

Invoke-Check "CSV file reading" {
    $code = @'
from utils.csv_handler import read_csv_rows

files = [
    "data/external/users.csv",
    "data/external/devices.csv",
    "data/external/consumables.csv",
    "data/external/cleaning_history.csv",
]
for path in files:
    rows = read_csv_rows(path)
    if not rows:
        raise SystemExit(f"{path} has no readable rows")
print("csv_reading_ok")
'@
    Invoke-ContainerPythonScript "csv_reading_check.py" $code
}

Invoke-Check "RAG no-result fallback" {
    $code = @'
from rag.rag_service import RagSummarizeService

query = "\u82f9\u679c\u624b\u673a\u5982\u4f55\u622a\u56fe"
expected = "\u77e5\u8bc6\u5e93\u4e2d\u672a\u68c0\u7d22\u5230\u8db3\u591f\u8d44\u6599"
text = RagSummarizeService().rag_summarize(query)
if expected not in text:
    raise SystemExit("RAG no-result fallback text not found")
if "sk-" in text or "DASHSCOPE_API_KEY=" in text:
    raise SystemExit("secret-like content detected")
print("rag_fallback_ok")
'@
    Invoke-ContainerPythonScript "rag_fallback_check.py" $code
}

Invoke-Check "Streamlit health" {
    $response = Invoke-WebRequest -UseBasicParsing $StreamlitHealthUrl
    $content = $response.Content.Trim()
    if ($content -ne "ok") {
        throw "unexpected health response: $content"
    }
    Write-Host "streamlit_health_ok"
}

Invoke-Check "Evaluations basic cases" {
    & docker compose exec -T $ServiceName python evaluations/run_basic_checks.py
    Assert-LastExitCode "evaluations/run_basic_checks.py"
}

Write-Host ""
if ($failures.Count -gt 0) {
    if (Test-Path $TempScriptDir) {
        Remove-Item -LiteralPath $TempScriptDir -Force
    }
    Write-Host "Project regression checks failed:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "- $failure" -ForegroundColor Red
    }
    exit 1
}

if (Test-Path $TempScriptDir) {
    Remove-Item -LiteralPath $TempScriptDir -Force
}
Write-Host "Project regression checks passed." -ForegroundColor Green
exit 0
