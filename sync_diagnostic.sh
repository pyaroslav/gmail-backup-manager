#!/bin/bash

echo "🔍 **Gmail Sync Diagnostic Tool**"
echo "=================================="

# Check if servers are running
echo "1. Checking server status..."
FRONTEND_RUNNING=$(ps aux | grep "http.server" | grep -v grep | wc -l)
BACKEND_RUNNING=$(ps aux | grep "uvicorn" | grep -v grep | wc -l)

if [ $FRONTEND_RUNNING -gt 0 ]; then
    echo "   ✅ Frontend server is running"
else
    echo "   ❌ Frontend server is NOT running"
fi

if [ $BACKEND_RUNNING -gt 0 ]; then
    echo "   ✅ Backend server is running"
else
    echo "   ❌ Backend server is NOT running"
    exit 1
fi

echo ""
echo "2. Checking current sync status..."
SYNC_STATUS=$(curl -s "http://localhost:8000/api/v1/test/sync/status")
echo "$SYNC_STATUS" | jq .

echo ""
echo "3. Checking emails count by year..."
EMAILS_COUNT=$(curl -s "http://localhost:8000/api/v1/test/sync/emails-count")
echo "$EMAILS_COUNT" | jq .

echo ""
echo "4. Testing Gmail API connection..."
GMAIL_CONNECTION=$(curl -s -X POST "http://localhost:8000/api/v1/test/sync/test-connection")
echo "$GMAIL_CONNECTION" | jq .

echo ""
echo "5. Testing Gmail API queries..."
GMAIL_QUERY=$(curl -s "http://localhost:8000/api/v1/test/sync/test-gmail-query")
echo "$GMAIL_QUERY" | jq .

echo ""
echo "6. Analyzing the issue..."
echo "=========================="

# Extract key values
DB_EMAILS=$(echo "$SYNC_STATUS" | jq -r '.total_emails_in_database')
GMAIL_EMAILS=$(echo "$GMAIL_CONNECTION" | jq -r '.total_emails_in_gmail')
API_ALL_EMAILS=$(echo "$GMAIL_QUERY" | jq -r '.gmail_api_results.all_emails')

echo "📊 **Summary:**"
echo "   Database emails: $DB_EMAILS"
echo "   Gmail API total: $GMAIL_EMAILS"
echo "   Gmail API all emails: $API_ALL_EMAILS"

echo ""
echo "🔍 **Issue Analysis:**"

if [ "$DB_EMAILS" -gt "$GMAIL_EMAILS" ]; then
    echo "   ❌ **PROBLEM IDENTIFIED:**"
    echo "   - Database has $DB_EMAILS emails"
    echo "   - Gmail API only shows $GMAIL_EMAILS emails"
    echo "   - This suggests Gmail API is not returning all emails"
    echo ""
    echo "   🎯 **Possible Causes:**"
    echo "   1. Gmail API scope limitations"
    echo "   2. Gmail account settings (IMAP/POP3 disabled)"
    echo "   3. Gmail API quota limits"
    echo "   4. Gmail account type restrictions"
    echo "   5. Gmail API version limitations"
    echo ""
    echo "   💡 **Solutions to Try:**"
    echo "   1. Check Gmail account settings"
    echo "   2. Verify Gmail API scopes"
    echo "   3. Check Gmail API quotas"
    echo "   4. Try different Gmail API queries"
    echo "   5. Check if Gmail account has restrictions"
else
    echo "   ✅ Database and Gmail API counts match"
fi

echo ""
echo "7. Checking Gmail API scopes..."
echo "================================"
echo "Current scope: https://www.googleapis.com/auth/gmail.readonly"
echo "This scope should allow reading ALL emails."

echo ""
echo "8. Recommendations..."
echo "===================="
echo ""
echo "🔧 **Immediate Actions:**"
echo "1. Check Gmail account settings in web interface"
echo "2. Verify IMAP is enabled in Gmail settings"
echo "3. Check Gmail API quotas in Google Cloud Console"
echo "4. Try accessing Gmail via web interface to see total email count"
echo ""
echo "🔍 **Debugging Steps:**"
echo "1. Open Gmail web interface"
echo "2. Check total email count in inbox"
echo "3. Check if emails from 2011-2022 are visible"
echo "4. Verify Gmail account type (personal vs workspace)"
echo ""
echo "📋 **Next Steps:**"
echo "1. If Gmail web shows more emails than API:"
echo "   - Check Gmail API quotas"
echo "   - Try different API queries"
echo "   - Consider Gmail account restrictions"
echo ""
echo "2. If Gmail web shows same count as API:"
echo "   - Emails might have been deleted/archived"
echo "   - Check Gmail trash and archive"
echo "   - Verify Gmail account history"
echo ""
echo "🚀 **Ready for investigation!**"
