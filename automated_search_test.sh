#!/bin/bash

echo "🔍 **Automated Search Email Detail Test**"
echo "========================================="

# Check if servers are running
echo "1. Checking server status..."
FRONTEND_RUNNING=$(ps aux | grep "http.server" | grep -v grep | wc -l)
BACKEND_RUNNING=$(ps aux | grep "uvicorn" | grep -v grep | wc -l)

if [ $FRONTEND_RUNNING -gt 0 ]; then
    echo "   ✅ Frontend server is running"
else
    echo "   ❌ Frontend server is NOT running"
    echo "   💡 Start it with: cd frontend && python3 -m http.server 3001"
    exit 1
fi

if [ $BACKEND_RUNNING -gt 0 ]; then
    echo "   ✅ Backend server is running"
else
    echo "   ❌ Backend server is NOT running"
    echo "   💡 Start it with: cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    exit 1
fi

# Test search API
echo ""
echo "2. Testing search API..."
SEARCH_RESPONSE=$(curl -s "http://localhost:8000/api/v1/test/emails/?page=1&page_size=3&search=test")
if [ $? -eq 0 ]; then
    SEARCH_COUNT=$(echo "$SEARCH_RESPONSE" | jq '.emails | length' 2>/dev/null || echo "0")
    echo "   ✅ Search API working (Found $SEARCH_COUNT emails with 'test')"
    
    if [ "$SEARCH_COUNT" -gt 0 ]; then
        EMAIL_ID=$(echo "$SEARCH_RESPONSE" | jq '.emails[0].id' 2>/dev/null || echo "null")
        EMAIL_SUBJECT=$(echo "$SEARCH_RESPONSE" | jq -r '.emails[0].subject' 2>/dev/null || echo "null")
        echo "   📧 Sample email: ID=$EMAIL_ID, Subject='$EMAIL_SUBJECT'"
    fi
else
    echo "   ❌ Search API failed"
    exit 1
fi

# Test frontend files
echo ""
echo "3. Testing frontend files..."
if curl -s "http://localhost:3001/" | grep -q "searchEmailDetailPanel"; then
    echo "   ✅ Search detail panel HTML found"
else
    echo "   ❌ Search detail panel HTML missing"
    exit 1
fi

if curl -s "http://localhost:3001/script.js" | grep -q "function selectSearchEmail"; then
    echo "   ✅ selectSearchEmail function found"
else
    echo "   ❌ selectSearchEmail function missing"
    exit 1
fi

# Test debug console page
echo ""
echo "4. Testing debug console page..."
if curl -s "http://localhost:3001/debug_console.html" | grep -q "Search Email Detail Debug Console"; then
    echo "   ✅ Debug console page accessible"
else
    echo "   ❌ Debug console page not accessible"
    exit 1
fi

echo ""
echo "🎯 **Manual Testing Instructions**"
echo "=================================="
echo ""
echo "✅ **All automated tests passed!**"
echo ""
echo "📋 **Next Steps for Manual Testing:**"
echo ""
echo "1. **Open Debug Console:**"
echo "   - Go to: http://localhost:3001/debug_console.html"
echo "   - This page will capture all console messages"
echo ""
echo "2. **Open Main Application:**"
echo "   - Go to: http://localhost:3001"
echo "   - Keep the debug console open in another tab"
echo ""
echo "3. **Test Search Functionality:**"
echo "   - Click 'Search' in the main app navigation"
echo "   - Enter search term: 'test'"
echo "   - Wait for search results to load"
echo "   - Click on any search result"
echo ""
echo "4. **Check Debug Console:**"
echo "   - Look at the console output in the debug page"
echo "   - Check for any error messages"
echo "   - Use the test buttons to run additional checks"
echo ""
echo "5. **Copy Results:**"
echo "   - Click 'Copy Console Output' in the debug page"
echo "   - Share the copied text with me"
echo ""
echo "🔧 **What to Look For:**"
echo "========================"
echo ""
echo "✅ **Expected Success Messages:**"
echo "   - 'showSearchResults called with: [...]'"
echo "   - 'currentSearchResults stored: [...]'"
echo "   - 'selectSearchEmail called with emailId: [id]'"
echo "   - 'Search email detail loaded for: [subject]'"
echo ""
echo "❌ **Error Messages to Report:**"
echo "   - 'Email not found in currentSearchResults'"
echo "   - 'Search detail panel elements not found'"
echo "   - 'currentSearchResults is empty'"
echo "   - Any red error messages"
echo ""
echo "📊 **Debug Information:**"
echo "========================="
echo "The debug page will show:"
echo "- Current search results count"
echo "- Search detail panel status"
echo "- Global functions status"
echo "- Last error message"
echo ""
echo "🚀 **Ready for manual testing!**"
echo "Please follow the steps above and share the console output."
