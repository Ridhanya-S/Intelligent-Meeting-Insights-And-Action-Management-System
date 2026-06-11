# Reminder System Documentation

## Overview

The reminder system automatically sends email notifications to action item owners when their deadlines are approaching. Reminders are sent 24 hours before the deadline (configurable).

## Automatic Reminders

**By default, reminders are sent automatically** in the background when the server is running.

### How It Works

1. **Background Scheduler**: When the FastAPI server starts, a background scheduler is initialized
2. **Periodic Checks**: The scheduler checks for pending reminders every hour (configurable)
3. **Automatic Sending**: If action items are found that need reminders, emails are sent automatically
4. **Trello Sync**: The system also checks Trello for manual deadline changes and uses updated deadlines

### Configuration

Set these environment variables to control automatic reminders:

```bash
# Enable/disable reminders (default: true)
REMINDER_ENABLED=true

# Enable/disable automatic background sending (default: true)
REMINDER_AUTO_SEND=true

# How often to check for reminders in minutes (default: 60)
REMINDER_CHECK_INTERVAL_MINUTES=60

# How many days before deadline to send reminder (default: 1)
REMINDER_DAYS_BEFORE=1
```

### Disabling Automatic Reminders

If you want to send reminders manually only:

```bash
REMINDER_AUTO_SEND=false
```

Then use the manual endpoint or script (see below).

## Manual Reminder Sending

### Option 1: API Endpoint

Send reminders manually via API:

```bash
curl -X POST http://localhost:8000/api/action-items/send-reminders
```

Response:
```json
{
  "success": true,
  "total": 5,
  "sent": 4,
  "failed": 1,
  "message": "Reminders sent: 4, Failed: 1"
}
```

### Option 2: Command Line Script

Run the reminder script directly:

```bash
python backend/send_reminders.py
```

### Option 3: Cron Job (Alternative)

If you prefer using cron instead of the built-in scheduler:

```bash
# Add to crontab (runs every hour)
0 * * * * cd /path/to/project && python backend/send_reminders.py
```

## Reminder Status

Check the reminder system status:

```bash
curl http://localhost:8000/api/action-items/reminder-status
```

Response:
```json
{
  "reminder_enabled": true,
  "auto_send_enabled": true,
  "check_interval_minutes": 60,
  "days_before_deadline": 1,
  "smtp_configured": true
}
```

## Reminder Methods

The system supports two methods for sending reminders:

### 1. Email Reminders (Primary Method)

If SMTP is configured, reminders are sent via email.

**Configuration Required:**
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com

# Map action item owners to email addresses
OWNER_EMAIL_MAP='{"John Doe": "john@example.com", "Jane Smith": "jane@example.com"}'
```

**Email Content Includes:**
- Action item description
- Assigned owner
- Deadline and time remaining
- Status
- Trello card link (if available)
- Dependencies and tags

### 2. Trello Comment Reminders (Fallback Method)

If SMTP is **not configured**, the system automatically falls back to adding reminder comments directly to Trello cards.

**No Additional Configuration Required** - Works automatically if:
- Trello API credentials are configured (`TRELLO_API_KEY` and `TRELLO_API_TOKEN`)
- Action item has a Trello card (`external_id` is set)

**Trello Comment Includes:**
- 🔔 REMINDER notification
- Assigned owner name
- Deadline and time remaining (hours and days)
- Status
- Full task details/description
- Dependencies (if any)
- Tags (if any)
- Direct card link (`https://trello.com/c/{card_id}`)
- Attempts to mention the owner (@username) if they're a board member

**How It Works:**
1. System checks if SMTP is configured
2. If SMTP available → Sends email reminder
3. If SMTP not available → Adds comment to Trello card
4. If email fails → Falls back to Trello comment
5. If neither available → Logs warning and skips reminder

**Example Trello Comment:**
```
🔔 REMINDER: Action Item Due Soon

**Assigned To:** John Doe
**Deadline:** 2025-11-29 14:00
**Time Remaining:** 12 hours (0 days)
**Status:** Doing

**Task Details:**
Complete the API integration testing

**Dependencies:**
- Backend API completion

**Tags:** frontend, high-priority

**Card Link:** https://trello.com/c/abc123xyz

Please ensure this action item is completed before the deadline.
```

## How Reminders Are Determined

An action item will receive a reminder if:

1. Status is `new`, `pending`, or `doing` (not `done` or `blocked`)
2. Deadline is set
3. Deadline is within 24 hours (and not past)
4. **For Email Reminders:** Owner has an email address configured in `OWNER_EMAIL_MAP`
5. **For Trello Comment Reminders:** Action item has a Trello card (`external_id` is set)
6. `REMINDER_ENABLED` is `true`

## Trello Integration

The system automatically syncs deadlines from Trello cards:

- If a deadline is changed manually in Trello UI
- The system detects the change during reminder checks
- Uses the updated deadline for reminder calculations
- No manual intervention needed

## Troubleshooting

### Reminders Not Sending

1. Check if reminders are enabled:
   ```bash
   curl http://localhost:8000/api/action-items/reminder-status
   ```

2. Check server logs for scheduler status:
   ```
   [Reminder Scheduler] Started - checking every 60 minutes
   ```

3. Verify SMTP configuration is correct

4. Check that action items have:
   - Valid deadlines
   - Owners with email addresses in `OWNER_EMAIL_MAP`

### Testing Reminders

1. Create a test action item with deadline 1 hour from now
2. Wait for next scheduler run (or trigger manually)
3. Check email inbox

### Manual Trigger for Testing

```bash
# Trigger immediately
curl -X POST http://localhost:8000/api/action-items/send-reminders
```

## Best Practices

1. **Keep server running**: Automatic reminders only work when the FastAPI server is running
2. **Monitor logs**: Check server logs for reminder sending status
3. **Email mapping**: Keep `OWNER_EMAIL_MAP` updated with current team members
4. **SMTP credentials**: Use app-specific passwords for Gmail (not regular passwords)
5. **Docker deployment**: Ensure scheduler runs in Docker container (it does by default)

## Production Deployment

For production, ensure:

1. Server runs continuously (use systemd, Docker, or process manager)
2. SMTP credentials are secure (use environment variables, not hardcoded)
3. Monitor reminder sending success/failure rates
4. Set appropriate `REMINDER_CHECK_INTERVAL_MINUTES` (60 minutes is reasonable)

## Example: Docker Deployment

The scheduler runs automatically in Docker:

```bash
docker-compose up -d
# Scheduler starts automatically with the server
```

Check logs:
```bash
docker-compose logs -f meeting-summarizer | grep "Reminder Scheduler"
```

