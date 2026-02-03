# PowerShell test runner script for Windows users

param(
    [Parameter(Position=0)]
    [string]$Command = "all",
    
    [switch]$Verbose,
    [switch]$Coverage,
    [switch]$Html
)

function Show-Help {
    Write-Host "PageSpeed Insights Audit Tool - Test Runner" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\run_tests.ps1 [command] [options]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Green
    Write-Host "  all              Run all tests (default)"
    Write-Host "  unit             Run unit tests only"
    Write-Host "  integration      Run integration tests only"
    Write-Host "  coverage         Run tests with coverage report"
    Write-Host "  install          Install test dependencies"
    Write-Host "  clean            Clean up test artifacts"
    Write-Host "  help             Show this help message"
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Green
    Write-Host "  -Verbose         Show verbose test output"
    Write-Host "  -Coverage        Generate coverage report"
    Write-Host "  -Html            Generate HTML coverage report"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\run_tests.ps1"
    Write-Host "  .\run_tests.ps1 unit -Verbose"
    Write-Host "  .\run_tests.ps1 coverage -Html"
}

function Install-Dependencies {
    Write-Host "Installing test dependencies..." -ForegroundColor Cyan
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    npm install
    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
}

function Run-AllTests {
    Write-Host "Running all tests..." -ForegroundColor Cyan
    
    $args = @()
    if ($Verbose) { $args += "-v" }
    if ($Coverage) {
        $args += "--cov=tools"
        $args += "--cov=run_audit"
        $args += "--cov-report=term-missing"
        $args += "--cov-report=xml"
        if ($Html) {
            $args += "--cov-report=html"
        }
    }
    
    pytest @args
}

function Run-UnitTests {
    Write-Host "Running unit tests..." -ForegroundColor Cyan
    
    $args = @("tests/unit/")
    if ($Verbose) { $args += "-v" }
    if ($Coverage) {
        $args += "--cov=tools"
        $args += "--cov-report=term-missing"
        if ($Html) {
            $args += "--cov-report=html"
        }
    }
    
    pytest @args
}

function Run-IntegrationTests {
    Write-Host "Running integration tests..." -ForegroundColor Cyan
    
    $args = @("tests/integration/")
    if ($Verbose) { $args += "-v" }
    if ($Coverage) {
        $args += "--cov=run_audit"
        $args += "--cov-report=term-missing"
        if ($Html) {
            $args += "--cov-report=html"
        }
    }
    
    pytest @args
}

function Run-Coverage {
    Write-Host "Running tests with coverage..." -ForegroundColor Cyan
    
    $args = @(
        "--cov=tools",
        "--cov=run_audit",
        "--cov-report=term-missing",
        "--cov-report=xml"
    )
    
    if ($Html) {
        $args += "--cov-report=html"
    }
    
    if ($Verbose) { $args += "-v" }
    
    pytest @args
    
    Write-Host ""
    Write-Host "Checking coverage threshold (70%)..." -ForegroundColor Cyan
    coverage report --fail-under=70
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Coverage threshold met!" -ForegroundColor Green
    } else {
        Write-Host "Coverage threshold not met!" -ForegroundColor Red
    }
    
    if ($Html) {
        Write-Host ""
        Write-Host "HTML coverage report generated in htmlcov/index.html" -ForegroundColor Green
    }
}

function Clean-Artifacts {
    Write-Host "Cleaning test artifacts..." -ForegroundColor Cyan
    
    $itemsToRemove = @(
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        "coverage.xml",
        "coverage.svg",
        "__pycache__"
    )
    
    foreach ($item in $itemsToRemove) {
        if (Test-Path $item) {
            Remove-Item -Path $item -Recurse -Force
            Write-Host "  Removed $item" -ForegroundColor Yellow
        }
    }
    
    Get-ChildItem -Path . -Include "__pycache__" -Recurse -Force | Remove-Item -Recurse -Force
    Get-ChildItem -Path . -Include "*.pyc" -Recurse -Force | Remove-Item -Force
    
    Write-Host "Cleanup complete!" -ForegroundColor Green
}

switch ($Command.ToLower()) {
    "all" {
        Run-AllTests
    }
    "unit" {
        Run-UnitTests
    }
    "integration" {
        Run-IntegrationTests
    }
    "coverage" {
        Run-Coverage
    }
    "install" {
        Install-Dependencies
    }
    "clean" {
        Clean-Artifacts
    }
    "help" {
        Show-Help
    }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}
