# Quick Test Guide: Real-Time Message Notifications

## Prerequisites
- Server running with Django Channels (ASGI)
- Redis or In-Memory channel layer (already configured)
- Two browsers or browser windows

## Step-by-Step Test

### Step 1: Start the Server
```bash
# In terminal, in project directory
uvicorn backend.asgi:application --reload --port 8000
```

Or if you're using runserver:
```bash
python manage.py runserver
```

### Step 2: Open Two Browser Windows

**Window A (User: Doctor or Staff)**
- Login as a doctor/staff member
- Navigate to: Messages → Inbox
- Keep browser console open (F12 → Console tab)

**Window B (User: Student or Another User)**
- Login as a different user (student/another staff member)
- Navigate to: Messages → Inbox
- Keep this window ready to send a message

### Step 3: Send a Test Message

**In Window B:**
1. Click "New direct message" button
2. Select the user from Window A as recipient
3. Type a test message: "Test real-time notification"
4. Click Send

### Step 4: Watch for Real-Time Updates

**In Window A - you should see:**

✅ **Within 1-2 seconds:**
- Navbar badge shows new unread count (green badge with number)
- Conversation appears in sidebar
- Unread count badge shows next to conversation name
- Last message preview shows "Test real-time notification"

✅ **Console messages:**
- "Connected to unread messages WebSocket" appears when page loads
- No error messages

### Step 5: Open the Conversation

**In Window A:**
1. Click the conversation in the sidebar
2. Message should appear immediately (this is existing functionality)
3. Mark as read
4. Go back to inbox
5. Unread badge in sidebar should disappear

### Step 6: Test Multiple Messages

**In Window B:**
- Send 3-4 more messages in quick succession
- Reply to messages from Window A back to Window B

**In Window A:**
- Watch the unread count update in real-time
- See the last message preview change each time
- Conversation should stay at top of sidebar

## Expected Behavior

| Action | Expected Result | Timeline |
|--------|-----------------|----------|
| Send message | Badge updates | <2 seconds |
| New convo | Appears in sidebar | <2 seconds |
| Multiple msgs | Count increments | <2 seconds each |
| Open conversation | Mark as read | Immediate |
| Badge disappears | When count = 0 | <1 second |

## Troubleshooting

### Badge not updating?
1. **Check WebSocket connection:**
   - Open browser DevTools (F12)
   - Go to Network → WS (WebSocket) tab
   - Should see: `ws://localhost:8000/ws/messages/unread/`
   - Status should be "101 Switching Protocols" (connected)

2. **If no WebSocket connection:**
   - Ensure server is running as ASGI, not WSGI
   - Check console for errors
   - Verify `channels` is installed: `pip list | grep channels`

3. **If connection is closed:**
   - Check server logs for errors
   - Server might be restarting (reload in dev mode restarts)
   - Try refreshing the page

### Message not appearing in chat?
- This is separate from real-time notifications
- Check the `ConversationConsumer` WebSocket (should be `ws://localhost:8000/ws/messages/CONV_ID/`)
- This typically means the message didn't send successfully

### High console.error messages?
- Normal during development
- Each time server restarts, WebSocket reconnects
- Up to 5 reconnect attempts with 1-5 second delays
- After 5 attempts, stops trying (requires page refresh)

## Advanced Testing

### Test WebSocket Directly
```javascript
// In browser console
const ws = new WebSocket('ws://localhost:8000/ws/messages/unread/');
ws.onmessage = (e) => console.log('Received:', JSON.parse(e.data));
ws.onopen = () => console.log('Connected!');
ws.onerror = (e) => console.log('Error:', e);
```

### Check for Race Conditions
1. Have two windows open to same conversation
2. Both send messages at same time
3. Both should see the other's message appear in real-time
4. Unread counts should be accurate

### Test Mobile
1. Open messaging on phone browser
2. Log in to clinic system
3. Have someone send you a message
4. Notification badge should update on phone screen

## Success Criteria

✅ Navbar badge appears when you receive a message  
✅ Navbar badge updates in real-time  
✅ Navbar badge disappears when you read all messages  
✅ Conversations appear/update in sidebar in real-time  
✅ Unread count shows per conversation  
✅ Last message preview updates  
✅ No console errors  
✅ Works on mobile browser  

## Performance Notes

- First notification: ~500ms-2 seconds (includes DB query)
- Subsequent notifications: <1 second
- Multiple users: Linear scaling (each recipient gets update)
- No noticeable performance impact on server

---

**Questions or issues?** Check the browser console (F12) and server logs for error messages.
