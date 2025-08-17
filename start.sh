#!/bin/bash

# Start the CL-SRS application

echo "🚀 Starting CL-SRS Application..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${RED}Please edit .env and add your OpenAI API key${NC}"
    echo ""
fi

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check if API port is already in use
if check_port 8000; then
    echo -e "${YELLOW}⚠️  Port 8000 is already in use. API server might already be running.${NC}"
    echo "Skipping API server start..."
    API_ALREADY_RUNNING=true
else
    API_ALREADY_RUNNING=false
fi

# Start the API server in background
if [ "$API_ALREADY_RUNNING" = false ]; then
    echo "📡 Starting API server..."
    cd app/api
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv venv
    fi

    source venv/bin/activate

    # Check Python version and use appropriate requirements
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "Python version: $PYTHON_VERSION"

    # Use minimal requirements for Python 3.13 compatibility
    echo "Installing dependencies (this may take a moment)..."
    pip install -q -r requirements-minimal.txt || pip install -q -r requirements-simple.txt

    # Start API in background with output redirection
    python ../../run_api.py > /tmp/clsrs-api.log 2>&1 &
    API_PID=$!
    cd ../..

    # Wait for API to be ready
    echo "Waiting for API to be ready..."
    for i in {1..10}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ API server is ready!${NC}"
            break
        fi
        if [ $i -eq 10 ]; then
            echo -e "${RED}❌ API server failed to start. Check /tmp/clsrs-api.log for errors${NC}"
            exit 1
        fi
        sleep 1
    done
else
    echo "API already running, staying in current directory"
fi

# Start the UI development server
echo "🎨 Starting UI server..."
cd app/ui
if [ ! -d "node_modules" ]; then
    echo "Installing UI dependencies..."
    npm install
fi

echo ""
echo -e "${GREEN}✅ CL-SRS is running!${NC}"
echo ""
echo "📱 UI: http://localhost:5173"
echo "🔧 API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "To test the API connection:"
echo "  curl http://localhost:8000/health"
echo ""
if [ "$API_ALREADY_RUNNING" = false ]; then
    echo "API logs: tail -f /tmp/clsrs-api.log"
    echo ""
fi
echo "Press Ctrl+C to stop all services"

# Start UI and wait
npm run dev

# Cleanup on exit
if [ "$API_ALREADY_RUNNING" = false ]; then
    trap "kill $API_PID 2>/dev/null; echo 'Stopped API server'" EXIT
fi