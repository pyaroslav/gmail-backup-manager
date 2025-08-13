#!/bin/bash

# Gmail Background Sync Service Manager
# This script provides easy management of the background sync service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/background_sync.log"
PID_FILE="$SCRIPT_DIR/background_sync.pid"
SYNC_SCRIPT="$SCRIPT_DIR/start_background_sync.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Gmail Background Sync Manager${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to check if service is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi
    return 1
}

# Function to start the service
start_service() {
    print_header
    print_status "Starting Gmail Background Sync Service..."
    
    if is_running; then
        print_warning "Service is already running (PID: $(cat $PID_FILE))"
        return 1
    fi
    
    # Check if backend is running
    if ! curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
        print_error "Backend server is not running. Please start the backend first."
        return 1
    fi
    
    # Start the background sync service
    cd "$SCRIPT_DIR"
    nohup python3 "$SYNC_SCRIPT" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    
    # Wait a moment to check if it started successfully
    sleep 2
    if is_running; then
        print_status "Service started successfully (PID: $pid)"
        print_status "Log file: $LOG_FILE"
        print_status "Use './manage_background_sync.sh status' to check status"
    else
        print_error "Failed to start service. Check log file: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to stop the service
stop_service() {
    print_header
    print_status "Stopping Gmail Background Sync Service..."
    
    if ! is_running; then
        print_warning "Service is not running"
        return 1
    fi
    
    local pid=$(cat "$PID_FILE")
    print_status "Sending stop signal to process $pid..."
    
    # Try graceful shutdown first
    kill -TERM "$pid" 2>/dev/null
    
    # Wait for graceful shutdown
    local count=0
    while [ $count -lt 10 ] && is_running; do
        sleep 1
        ((count++))
    done
    
    # Force kill if still running
    if is_running; then
        print_warning "Force killing process..."
        kill -KILL "$pid" 2>/dev/null
        sleep 1
    fi
    
    if ! is_running; then
        print_status "Service stopped successfully"
        rm -f "$PID_FILE"
    else
        print_error "Failed to stop service"
        return 1
    fi
}

# Function to restart the service
restart_service() {
    print_header
    print_status "Restarting Gmail Background Sync Service..."
    
    stop_service
    sleep 2
    start_service
}

# Function to show status
show_status() {
    print_header
    
    if is_running; then
        local pid=$(cat "$PID_FILE")
        print_status "Service is running (PID: $pid)"
        
        # Get sync status from API
        echo ""
        print_status "Sync Status:"
        if curl -s "http://localhost:8000/api/v1/test/background-sync/status" > /dev/null 2>&1; then
            curl -s "http://localhost:8000/api/v1/test/background-sync/status" | jq '.sync_status' 2>/dev/null || echo "Unable to parse sync status"
        else
            print_warning "Unable to connect to API"
        fi
        
        # Show recent log entries
        echo ""
        print_status "Recent log entries:"
        if [ -f "$LOG_FILE" ]; then
            tail -10 "$LOG_FILE" | while read line; do
                echo "  $line"
            done
        else
            print_warning "No log file found"
        fi
    else
        print_warning "Service is not running"
    fi
}

# Function to show logs
show_logs() {
    print_header
    print_status "Showing recent logs..."
    
    if [ -f "$LOG_FILE" ]; then
        if [ "$1" = "follow" ]; then
            print_status "Following logs (Ctrl+C to stop)..."
            tail -f "$LOG_FILE"
        else
            tail -50 "$LOG_FILE"
        fi
    else
        print_warning "No log file found"
    fi
}

# Function to show help
show_help() {
    print_header
    echo "Usage: $0 {start|stop|restart|status|logs|logs-follow}"
    echo ""
    echo "Commands:"
    echo "  start         Start the background sync service"
    echo "  stop          Stop the background sync service"
    echo "  restart       Restart the background sync service"
    echo "  status        Show service status and recent logs"
    echo "  logs          Show recent log entries"
    echo "  logs-follow   Follow log entries in real-time"
    echo "  help          Show this help message"
    echo ""
    echo "The service will sync emails every 5 minutes automatically."
    echo "Logs are written to: $LOG_FILE"
}

# Main script logic
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    logs-follow)
        show_logs follow
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
