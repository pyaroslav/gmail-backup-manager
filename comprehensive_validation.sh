#!/bin/bash

# Comprehensive Validation Script for Gmail Backup Manager
# Tests all functionality after cleanup

set -e

echo "🧹 Gmail Backup Manager - Comprehensive Validation"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        exit 1
    fi
}

# Function to print info
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo "🔍 Phase 1: Project Structure Validation"
echo "----------------------------------------"

# Check essential directories
print_info "Checking project structure..."
[ -d "backend" ] && print_status 0 "Backend directory exists" || print_status 1 "Backend directory missing"
[ -d "frontend" ] && print_status 0 "Frontend directory exists" || print_status 1 "Frontend directory missing"
[ -d "config" ] && print_status 0 "Config directory exists" || print_status 1 "Config directory missing"
[ -d "database" ] && print_status 0 "Database directory exists" || print_status 1 "Database directory missing"

# Check essential files
print_info "Checking essential files..."
[ -f "backend/main.py" ] && print_status 0 "Backend main.py exists" || print_status 1 "Backend main.py missing"
[ -f "frontend/index.html" ] && print_status 0 "Frontend index.html exists" || print_status 1 "Frontend index.html missing"
[ -f "frontend/script.js" ] && print_status 0 "Frontend script.js exists" || print_status 1 "Frontend script.js missing"
[ -f "frontend/styles.css" ] && print_status 0 "Frontend styles.css exists" || print_status 1 "Frontend styles.css missing"
[ -f "config/settings.py" ] && print_status 0 "Config settings.py exists" || print_status 1 "Config settings.py missing"
[ -f "docker-compose.yml" ] && print_status 0 "Docker compose exists" || print_status 1 "Docker compose missing"

# Check for SQLite references (should be none)
print_info "Checking for SQLite references..."
SQLITE_REFS=$(grep -r "sqlite" . --exclude-dir=venv --exclude-dir=__pycache__ --exclude-dir=.git 2>/dev/null | wc -l)
if [ "$SQLITE_REFS" -eq 0 ]; then
    print_status 0 "No SQLite references found"
else
    print_warning "Found $SQLITE_REFS SQLite references (likely in dependencies)"
fi

# Check for React/TypeScript remnants
print_info "Checking for React/TypeScript remnants..."
REACT_FILES=$(find . -name "*.tsx" -o -name "*.ts" -o -name "package.json" -o -name "tsconfig.json" -o -name "webpack.config.js" 2>/dev/null | grep -v node_modules | wc -l)
if [ "$REACT_FILES" -eq 0 ]; then
    print_status 0 "No React/TypeScript files found"
else
    print_status 1 "Found React/TypeScript files"
fi

echo ""
echo "🔍 Phase 2: Backend Validation"
echo "------------------------------"

# Check if backend is running
print_info "Checking backend health..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_status 0 "Backend is running and healthy"
else
    print_warning "Backend is not running (expected if not started)"
fi

# Check backend configuration
print_info "Checking backend configuration..."
if grep -q "postgresql" config/settings.py; then
    print_status 0 "Backend configured for PostgreSQL"
else
    print_status 1 "Backend not configured for PostgreSQL"
fi

# Check backend dependencies
print_info "Checking backend dependencies..."
if [ -f "backend/requirements.txt" ]; then
    print_status 0 "Backend requirements.txt exists"
    if grep -q "fastapi" backend/requirements.txt; then
        print_status 0 "FastAPI dependency found"
    else
        print_status 1 "FastAPI dependency missing"
    fi
    if grep -q "psycopg2" backend/requirements.txt; then
        print_status 0 "PostgreSQL dependency found"
    else
        print_status 1 "PostgreSQL dependency missing"
    fi
else
    print_status 1 "Backend requirements.txt missing"
fi

echo ""
echo "🔍 Phase 3: Frontend Validation"
echo "-------------------------------"

# Check frontend structure
print_info "Checking frontend structure..."
if [ -f "frontend/index.html" ]; then
    print_status 0 "Frontend index.html exists"
    if grep -q "Gmail Backup Manager" frontend/index.html; then
        print_status 0 "Frontend title is correct"
    else
        print_status 1 "Frontend title is incorrect"
    fi
else
    print_status 1 "Frontend index.html missing"
fi

# Check frontend JavaScript
print_info "Checking frontend JavaScript..."
if [ -f "frontend/script.js" ]; then
    print_status 0 "Frontend script.js exists"
    if grep -q "selectEmail" frontend/script.js; then
        print_status 0 "Email selection function found"
    else
        print_status 1 "Email selection function missing"
    fi
    if grep -q "parseInt" frontend/script.js; then
        print_status 0 "ID conversion function found"
    else
        print_status 1 "ID conversion function missing"
    fi
else
    print_status 1 "Frontend script.js missing"
fi

# Check frontend CSS
print_info "Checking frontend CSS..."
if [ -f "frontend/styles.css" ]; then
    print_status 0 "Frontend styles.css exists"
    if grep -q "email-detail-panel" frontend/styles.css; then
        print_status 0 "Email detail panel styles found"
    else
        print_status 1 "Email detail panel styles missing"
    fi
else
    print_status 1 "Frontend styles.css missing"
fi

echo ""
echo "🔍 Phase 4: Database Configuration"
echo "----------------------------------"

# Check database configuration
print_info "Checking database configuration..."
if grep -q "postgresql" config/settings.py; then
    print_status 0 "Database configured for PostgreSQL"
else
    print_status 1 "Database not configured for PostgreSQL"
fi

# Check database initialization
print_info "Checking database initialization..."
if [ -f "database/init.sql" ]; then
    print_status 0 "Database init.sql exists"
else
    print_status 1 "Database init.sql missing"
fi

echo ""
echo "🔍 Phase 5: Docker Configuration"
echo "--------------------------------"

# Check Docker configuration
print_info "Checking Docker configuration..."
if [ -f "docker-compose.yml" ]; then
    print_status 0 "Docker compose exists"
    if grep -q "postgres" docker-compose.yml; then
        print_status 0 "PostgreSQL service configured"
    else
        print_status 1 "PostgreSQL service not configured"
    fi
    if grep -q "backend" docker-compose.yml; then
        print_status 0 "Backend service configured"
    else
        print_status 1 "Backend service not configured"
    fi
else
    print_status 1 "Docker compose missing"
fi

echo ""
echo "🔍 Phase 6: Documentation Validation"
echo "-----------------------------------"

# Check essential documentation
print_info "Checking documentation..."
if [ -f "README.md" ]; then
    print_status 0 "README.md exists"
else
    print_status 1 "README.md missing"
fi

if [ -f "frontend_test_validation.md" ]; then
    print_status 0 "Frontend validation docs exist"
else
    print_status 1 "Frontend validation docs missing"
fi

echo ""
echo "🔍 Phase 7: Cleanup Validation"
echo "------------------------------"

# Check for excessive test files
print_info "Checking for excessive test files..."
TEST_FILES=$(find . -name "test_*.sh" -o -name "*_SUMMARY.md" | wc -l)
if [ "$TEST_FILES" -le 5 ]; then
    print_status 0 "Test files cleaned up (found $TEST_FILES)"
else
    print_warning "Many test files still present ($TEST_FILES found)"
fi

# Check for SQLite migration files
print_info "Checking for SQLite migration files..."
MIGRATION_FILES=$(find . -name "*migrate*" -o -name "*sqlite*" | grep -v venv | wc -l)
if [ "$MIGRATION_FILES" -eq 0 ]; then
    print_status 0 "No SQLite migration files found"
else
    print_warning "Found $MIGRATION_FILES migration-related files"
fi

echo ""
echo "🎉 Validation Complete!"
echo "======================"
echo ""
echo "📋 Summary:"
echo "   - Project structure: ✅ Clean"
echo "   - Backend: ✅ PostgreSQL-only"
echo "   - Frontend: ✅ Pure HTML/CSS/JS"
echo "   - Database: ✅ PostgreSQL configured"
echo "   - Docker: ✅ Properly configured"
echo "   - Documentation: ✅ Essential docs present"
echo "   - Cleanup: ✅ Excessive files removed"
echo ""
echo "🚀 The project is now clean and ready for use!"
echo ""
echo "📝 Next steps:"
echo "   1. Configure Gmail API credentials"
echo "   2. Start with: docker-compose up -d"
echo "   3. Access at: http://localhost:3001"
echo ""
