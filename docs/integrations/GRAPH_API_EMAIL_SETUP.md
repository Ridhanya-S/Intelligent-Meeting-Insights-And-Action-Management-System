# Microsoft Graph API Email Setup (Delegated Permissions)

This guide explains how to set up Microsoft Graph API for sending emails using delegated permissions.

## Overview

Delegated permissions allow the application to send emails on behalf of an authenticated user. This is more secure than application permissions and doesn't require admin consent for each mailbox.

## Prerequisites

1. Microsoft 365 tenant
2. Azure App Registration with:
   - `MS_GRAPH_TENANT_ID`
   - `MS_GRAPH_CLIENT_ID`
   - `MS_GRAPH_CLIENT_SECRET`
3. Delegated permission: `Mail.Send`

## Step 1: Configure Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Select your app (or create a new one)
4. Go to **API permissions**
5. Click **Add a permission** → **Microsoft Graph** → **Delegated permissions**
6. Search for and select `Mail.Send`
7. Click **Add permissions**
8. **Important**: Click **Grant admin consent** (if required by your organization)

## Step 2: Obtain Refresh Token (One-Time Setup)

You need to obtain a refresh token using device code flow. This is a one-time setup.

### Option A: Using Python Script

Create a script `get_refresh_token.py`:

```python
import requests
import time

TENANT_ID = "your-tenant-id"
CLIENT_ID = "your-client-id"

# Step 1: Get device code
device_code_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode"
device_data = {
    "client_id": CLIENT_ID,
    "scope": "https://graph.microsoft.com/Mail.Send offline_access"
}

response = requests.post(device_code_url, data=device_data)
device_info = response.json()

print("\n" + "="*60)
print("DEVICE CODE AUTHENTICATION")
print("="*60)
print(f"\nGo to: {device_info['verification_uri']}")
print(f"Enter code: {device_info['user_code']}")
print(f"\nThis code expires in {device_info['expires_in']} seconds")
print("\nWaiting for you to authenticate...")

# Step 2: Poll for token
token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
device_code = device_info['device_code']
interval = device_info.get('interval', 5)
expires_in = device_info.get('expires_in', 900)

start_time = time.time()
while time.time() - start_time < expires_in:
    token_data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": CLIENT_ID,
        "device_code": device_code
    }
    
    response = requests.post(token_url, data=token_data)
    result = response.json()
    
    if "access_token" in result:
        print("\n✅ Authentication successful!")
        print(f"\nRefresh Token:")
        print(result['refresh_token'])
        print("\n⚠️  IMPORTANT: Save this refresh token securely!")
        print("Add it to your .env file as:")
        print(f"MS_GRAPH_REFRESH_TOKEN={result['refresh_token']}")
        break
    elif result.get("error") == "authorization_pending":
        print(f"⏳ Waiting... ({int(time.time() - start_time)}s elapsed)", end='\r')
        time.sleep(interval)
    elif result.get("error") == "slow_down":
        interval += 5
        time.sleep(interval)
    else:
        print(f"\n❌ Error: {result.get('error_description', 'Unknown error')}")
        break
```

Run the script:
```bash
python get_refresh_token.py
```

Follow the instructions to authenticate and copy the refresh token.

### Option B: Using Browser Flow

For interactive setup, you can use a browser-based OAuth flow:

1. Construct authorization URL:
```
https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize?
  client_id={CLIENT_ID}
  &response_type=code
  &redirect_uri=http://localhost:8000/auth/callback
  &response_mode=query
  &scope=https://graph.microsoft.com/Mail.Send offline_access
  &state=12345
```

2. After authentication, exchange the authorization code for tokens:
```python
token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": authorization_code,
    "redirect_uri": "http://localhost:8000/auth/callback",
    "grant_type": "authorization_code"
}
response = requests.post(token_url, data=data)
refresh_token = response.json()['refresh_token']
```

## Step 3: Configure Environment Variables

Add the refresh token to your `.env` file:

```bash
# Microsoft Graph API (already configured)
MS_GRAPH_TENANT_ID=your-tenant-id
MS_GRAPH_CLIENT_ID=your-client-id
MS_GRAPH_CLIENT_SECRET=your-client-secret

# Refresh token for delegated permissions (NEW)
MS_GRAPH_REFRESH_TOKEN=your-refresh-token-here

# Email sender (must be the authenticated user's email)
EMAIL_FROM=your-email@yourdomain.com
```

## Step 4: Verify Setup

The system will automatically:
1. Use the refresh token to get an access token
2. Use the access token to send emails via Graph API
3. Refresh the token automatically when it expires

## How It Works

1. **Initial Setup**: User authenticates once via device code flow
2. **Refresh Token**: Stored securely in `.env` file
3. **Access Token**: Automatically obtained using refresh token
4. **Token Refresh**: System automatically refreshes expired tokens
5. **Email Sending**: Uses `/me/sendMail` endpoint with delegated permissions

## Token Refresh

The refresh token is long-lived but can expire. If you get authentication errors:

1. Run the device code flow again to get a new refresh token
2. Update `MS_GRAPH_REFRESH_TOKEN` in your `.env` file
3. Restart the application

## Security Notes

- **Refresh Token**: Keep it secure! It allows access to send emails on behalf of the authenticated user
- **Delegated Permissions**: The app can only send emails as the authenticated user
- **Token Storage**: Refresh tokens are stored in `.env` file - ensure it's not committed to version control
- **Scope**: Only requests `Mail.Send` permission - minimal permissions required

## Troubleshooting

### Error: "refresh token expired"
- Obtain a new refresh token using device code flow
- Update `MS_GRAPH_REFRESH_TOKEN` in `.env`

### Error: "Permission denied"
- Ensure `Mail.Send` delegated permission is granted
- Ensure admin consent is provided (if required)
- Verify the authenticated user has permission to send emails

### Error: "Invalid client"
- Verify `MS_GRAPH_CLIENT_ID` and `MS_GRAPH_CLIENT_SECRET` are correct
- Ensure the app registration exists in Azure Portal

## Benefits of Delegated Permissions

- ✅ More secure (user-level permissions)
- ✅ No admin consent needed for each mailbox
- ✅ Works with any user mailbox in the tenant
- ✅ Better audit trail (emails sent on behalf of specific user)
- ✅ No need for Application Access Policies

