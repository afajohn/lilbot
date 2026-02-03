#!/bin/bash

# Bash test runner script for Unix/Linux/Mac users

set -e

VERBOSE=""
COVERAGE=""
HTML=""

show_help() {
    echo -e "\033[36mPageSpeed Insights Audit Tool - Test Runner\033[0m"
    echo ""
    echo -e "\033[33mUsage: ./run_tests.sh [command] [options]\033[0m"
    echo ""
    echo -e "\033[32mCommands:\033[0m"
    echo "  all              Run all tests (default)"
    echo "  unit             Run unit tests only"
    echo "  integration      Run integration tests only"
    echo "  coverage         Run tests with coverage report"
    echo "  install          Install test dependencies"
    echo "  clean            Clean up test artifacts"
    echo "  help             Show this help message"
    echo ""
    echo -e "\033[32mOptions:\033[0m"
    echo "  --verbose        Show verbose test output"
    echo "  --coverage       Generate coverage report"
    echo "  --html           Generate HTML coverage report"
    echo ""
    echo -e "\033[33mExamples:\033[0m"
    echo "  ./run_tests.sh"
    echo "  ./run_tests.sh unit --verbose"
    echo "  ./run_tests.sh coverage --html"
}

install_dependencies() {
    echo -e "\033[36mInstalling test dependencies...\033[0m"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    npm install
    echo -e "\033[32mDependencies installed successfully!\033[0m"
}

run_all_tests() {
    echo -e "\033[36mRunning all tests...\033[0m"
    
    ARGS=""
    if [ -n "$VERBOSE" ]; then
        ARGS="$ARGS -v"
    fi
    if [ -n "$COVERAGE" ]; then
        ARGS="$ARGS --cov=tools --cov=run_audit --cov-report=term-missing --cov-report=xml"
        if [ -n "$HTML" ]; then
            ARGS="$ARGS --cov-report=html"
        fi
    fi
    
    pytest $ARGS
}

run_unit_tests() {
    echo -e "\033[36mRunning unit tests...\033[0m"
    
    ARGS="tests/unit/"
    if [ -n "$VERBOSE" ]; then
        ARGS="$ARGS -v"
    fi
    if [ -n "$COVERAGE" ]; then
        ARGS="$ARGS --cov=tools --cov-report=term-missing"
        if [ -n "$HTML" ]; then
            ARGS="$ARGS --cov-report=html"
        fi
    fi
    
    pytest $ARGS
}

run_integration_tests() {
    echo -e "\033[36mRunning integration tests...\033[0m"
    
    ARGS="tests/integration/"
    if [ -n "$VERBOSE" ]; then
        ARGS="$ARGS -v"
    fi
    if [ -n "$COVERAGE" ]; then
        ARGS="$ARGS --cov=run_audit --cov-report=term-missing"
        if [ -n "$HTML" ]; then
            ARGS="$ARGS --cov-report=html"
        fi
    fi
    
    pytest $ARGS
}

run_coverage() {
    echo -e "\033[36mRunning tests with coverage...\033[0m"
    
    ARGS="--cov=tools --cov=run_audit --cov-report=term-missing --cov-report=xml"
    
    if [ -n "$HTML" ]; then
        ARGS="$ARGS --cov-report=html"
    fi
    
    if [ -n "$VERBOSE" ]; then
        ARGS="$ARGS -v"
    fi
    
    pytest $ARGS
    
    echo ""
    echo -e "\033[36mChecking coverage threshold (70%)...\033[0m"
    if coverage report --fail-under=70; then
        echo -e "\033[32mCoverage threshold met!\033[0m"
    else
        echo -e "\033[31mCoverage threshold not met!\033[0m"
        exit 1
    fi
    
    if [ -n "$HTML" ]; then
        echo ""
        echo -e "\033[32mHTML coverage report generated in htmlcov/index.html\033[0m"
    fi
}

clean_artifacts() {
    echo -e "\033[36mCleaning test artifacts...\033[0m"
    
    rm -rf .pytest_cache .coverage htmlcov coverage.xml coverage.svg __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    
    echo -e "\033[32mCleanup complete!\033[0m"
}

COMMAND="${1:-all}"
shift || true

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE="yes"
            shift
            ;;
        --coverage)
            COVERAGE="yes"
            shift
            ;;
        --html)
            HTML="yes"
            shift
            ;;
        *)
            echo -e "\033[31mUnknown option: $1\033[0m"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

case $COMMAND in
    all)
        run_all_tests
        ;;
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    coverage)
        COVERAGE="yes"
        run_coverage
        ;;
    install)
        install_dependencies
        ;;
    clean)
        clean_artifacts
        ;;
    help)
        show_help
        ;;
    *)
        echo -e "\033[31mUnknown command: $COMMAND\033[0m"
        echo ""
        show_help
        exit 1
        ;;
esac
