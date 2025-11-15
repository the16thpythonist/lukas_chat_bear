#!/bin/bash
# Test runner script for dashboard
# Runs all backend and frontend tests with coverage reporting

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Lukas Dashboard Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print section headers
print_header() {
    echo -e "\n${GREEN}➜ $1${NC}\n"
}

# Function to print errors
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print warnings
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Change to dashboard directory
cd "$(dirname "$0")"

# Parse command line arguments
RUN_BACKEND=true
RUN_FRONTEND=false
RUN_COVERAGE=false
RUN_UNIT_ONLY=false
RUN_INTEGRATION_ONLY=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --backend-only) RUN_FRONTEND=false ;;
        --frontend-only) RUN_BACKEND=false; RUN_FRONTEND=true ;;
        --coverage) RUN_COVERAGE=true ;;
        --unit) RUN_UNIT_ONLY=true ;;
        --integration) RUN_INTEGRATION_ONLY=true ;;
        --help)
            echo "Usage: ./run-tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  --backend-only     Run only backend tests"
            echo "  --frontend-only    Run only frontend tests"
            echo "  --coverage         Generate coverage reports"
            echo "  --unit             Run only unit tests"
            echo "  --integration      Run only integration tests"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Backend tests
if [ "$RUN_BACKEND" = true ]; then
    print_header "Running Backend Tests"

    cd backend

    # Check if pytest is installed
    if ! python -m pytest --version &> /dev/null; then
        print_error "pytest not installed. Installing dependencies..."
        pip install -r requirements.txt
    fi

    # Determine what to run
    TEST_PATH="tests/"
    if [ "$RUN_UNIT_ONLY" = true ]; then
        TEST_PATH="tests/unit/"
        echo "Running unit tests only..."
    elif [ "$RUN_INTEGRATION_ONLY" = true ]; then
        TEST_PATH="tests/integration/"
        echo "Running integration tests only..."
    fi

    # Run tests
    if [ "$RUN_COVERAGE" = true ]; then
        print_warning "Running with coverage reporting..."
        python -m pytest "$TEST_PATH" \
            --cov=backend \
            --cov-report=html \
            --cov-report=term \
            -v
        print_success "Coverage report generated at: backend/htmlcov/index.html"
    else
        python -m pytest "$TEST_PATH" -v
    fi

    if [ $? -eq 0 ]; then
        print_success "Backend tests passed!"
    else
        print_error "Backend tests failed!"
        exit 1
    fi

    cd ..
fi

# Frontend tests
if [ "$RUN_FRONTEND" = true ]; then
    print_header "Running Frontend Tests"

    cd frontend

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_warning "node_modules not found. Installing dependencies..."
        npm install
    fi

    # Run tests
    if [ "$RUN_COVERAGE" = true ]; then
        print_warning "Running with coverage reporting..."
        npm run test:coverage
        print_success "Coverage report generated at: frontend/coverage/index.html"
    else
        npm run test
    fi

    if [ $? -eq 0 ]; then
        print_success "Frontend tests passed!"
    else
        print_error "Frontend tests failed!"
        exit 1
    fi

    cd ..
fi

# Final summary
echo ""
print_header "Test Summary"
if [ "$RUN_BACKEND" = true ]; then
    print_success "Backend tests completed"
fi
if [ "$RUN_FRONTEND" = true ]; then
    print_success "Frontend tests completed"
fi
echo ""
print_success "All tests passed! 🎉"
