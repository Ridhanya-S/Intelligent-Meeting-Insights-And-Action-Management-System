# API Bearer Token Authentication

## Overview

The API now supports Bearer Token authentication for securing endpoints that expose database data to external applications.

## Configuration

Set the `API_BEARER_TOKEN` environment variable to enable authentication:

```bash
export API_BEARER_TOKEN="your-secret-token-here"
```

Or add it to your `.env` file:

```
API_BEARER_TOKEN=your-secret-token-here
```

**Note:** If `API_BEARER_TOKEN` is not set, authentication is disabled (development mode). In production, always set this token.

## Protected Endpoints

The following endpoints require Bearer Token authentication:

### Summaries
- `GET /api/summaries/{summary_id}` - Get a specific summary
- `GET /api/summaries/project/{project_name}` - Get all summaries for a project
- `DELETE /api/summaries/{summary_id}` - Delete a summary

### Action Items
- `GET /api/action-items/` - Get action items (with filters)
- `POST /api/action-items/send-reminders` - Send reminders
- `GET /api/action-items/reminder-status` - Get reminder status

### Projects
- `GET /api/projects` - Get list of all projects
- `POST /api/projects` - Create a new project
- `DELETE /api/projects/{project_name}` - Delete a project
- `POST /api/projects/{project_name}/extract-emails` - Extract emails
- `POST /api/projects/{project_name}/sync-confluence` - Sync Confluence pages
- `GET /api/projects/{project_name}/email-mappings` - Get email mappings

## Public Endpoints

The following endpoints remain public (no authentication required):

- `GET /` - Frontend page
- `GET /health` - Health check
- `POST /api/transcripts/process` - Process transcript (file upload)
- `POST /api/transcripts/process-sharepoint-url` - Process SharePoint URL
- `GET /api/transcripts/process/{process_id}/progress` - Get processing progress
- `POST /api/transcripts/process/{process_id}/skip` - Skip processing
- `POST /api/transcripts/process/confirm` - Confirm processing

## Usage Examples

### Using curl

```bash
# With bearer token
curl -H "Authorization: Bearer your-secret-token-here" \
     http://localhost:8000/api/summaries/{summary_id}

# Without token (will fail if API_BEARER_TOKEN is set)
curl http://localhost:8000/api/summaries/{summary_id}
```

### Using Python requests

```python
import requests

headers = {
    "Authorization": "Bearer your-secret-token-here"
}

response = requests.get(
    "http://localhost:8000/api/summaries/{summary_id}",
    headers=headers
)
```

### Using JavaScript fetch

```javascript
fetch('http://localhost:8000/api/summaries/{summary_id}', {
    headers: {
        'Authorization': 'Bearer your-secret-token-here'
    }
})
.then(response => response.json())
.then(data => console.log(data));
```

## Error Responses

### 401 Unauthorized
Returned when no bearer token is provided:

```json
{
    "detail": "Authentication required. Please provide a valid bearer token."
}
```

### 403 Forbidden
Returned when an invalid bearer token is provided:

```json
{
    "detail": "Invalid bearer token. Access denied."
}
```

## Security Best Practices

1. **Use a strong, random token**: Generate a secure random token (at least 32 characters)
   ```bash
   # Generate a random token
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Store tokens securely**: Never commit tokens to version control. Use environment variables or secure secret management.

3. **Rotate tokens regularly**: Change your bearer token periodically, especially if it's been compromised.

4. **Use HTTPS in production**: Always use HTTPS when transmitting bearer tokens over the network.

5. **Limit token scope**: Consider implementing different tokens for different applications if needed.

## Development vs Production

- **Development**: If `API_BEARER_TOKEN` is not set, authentication is disabled for easier development.
- **Production**: Always set `API_BEARER_TOKEN` to secure your API endpoints.


