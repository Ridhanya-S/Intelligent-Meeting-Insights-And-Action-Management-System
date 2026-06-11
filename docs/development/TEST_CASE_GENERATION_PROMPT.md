# Test Case Generation Prompt - Meeting Summarizer POC

## 📋 Complete Test Case Generation Template

Use this prompt template when you need to generate test cases for new features or enhancements to the Meeting Summarizer POC application.

---

## ✍️ Test Case Generation Prompt Template

```
Please act as a Senior QA Engineer with expertise in API testing, security validation, and 
edge case identification. I need you to generate a comprehensive set of test cases for a 
new feature in my Meeting Summarizer POC application.

APPLICATION CONTEXT:
The Meeting Summarizer POC is a Python-based application that processes Microsoft Teams 
meeting recordings/transcripts to generate structured, actionable summaries using AI (GPT models).

FEATURE TO TEST:
[Briefly describe the new feature's primary function in one sentence]
Example: "Process a Teams meeting recording URL and return an AI-generated summary with action items"

FEATURE SPECIFICATION:
Input: [What input does it take?]
Example: "A POST request containing: teams_url (string, required), project_name (string, required), 
meeting_title (string, optional), skip_sync (boolean, optional)"

Output: [What is the expected output?]
Example: "A JSON object containing: summary_id, meeting_title, meeting_date, overall_summary, 
action_items (with owner, deadline, status), decisions, risks, trello_board_url, confluence_page_url"

Expected Behavior: [Describe the processing flow]
Example: "The system validates the URL, extracts meeting details via Microsoft Graph API, 
downloads the recording from SharePoint, transcribes it using Whisper, generates a summary 
using GPT, extracts action items/decisions/risks, stores in SQLite database, syncs to Trello 
and Confluence, and returns the summary data"

EXISTING SYSTEM CONSTRAINTS:
Based on the Meeting Summarizer POC documentation, these constraints must be respected:

1. URL Validation:
   - ONLY Microsoft Teams URLs are accepted
   - Rejected platforms: Zoom, Google Meet, Webex, GoToMeeting, Skype, Whereby, Jitsi, 
     BigBlueButton, RingCentral, and any other non-Teams platforms
   - Must use HTTPS protocol
   - Cannot be empty, null, or whitespace-only

2. File Constraints:
   - Maximum file size: 500MB (configurable)
   - Allowed formats: .txt, .md, .json, .srt, .vtt (text), .mp3, .wav, .m4a, .flac, 
     .ogg, .aac, .wma (audio), .mp4, .avi, .mov, .mkv, .webm, .flv, .wmv (video)
   - Files must be readable and non-corrupt

3. AI Model Constraints:
   - OpenAI GPT model: Maximum 4000 tokens per request
   - Whisper model: Handles audio/video transcription
   - Transcripts can be long; chunking may be required

4. Database Constraints:
   - SQLite database
   - Duplicate detection via SHA-256 file hash (project-scoped)
   - Foreign key relationships must be maintained

5. External Integration Constraints:
   - Trello sync: Optional, graceful degradation if unavailable
   - Confluence sync: Optional, graceful degradation if unavailable
   - Microsoft Graph API: Required for Teams URL processing
   - SharePoint: Required for recording downloads

6. Security Constraints:
   - Bearer token authentication (if configured)
   - Input sanitization required (project names, meeting titles)
   - SQL injection prevention (parameterized queries)
   - Path traversal prevention
   - File type validation

7. Status Management:
   - Action item statuses: NEW, PENDING, DOING, DONE, BLOCKED
   - Old status values must be migrated: todo→PENDING, in_progress→DOING, completed→DONE

TASK:
Generate a minimum of 20 test cases categorized into the following types:

1. Functional Tests (Happy Path): Verify the feature meets specified requirements with valid inputs
2. Validation Tests (Input): Ensure proper validation of all input parameters
3. Negative Tests: Test invalid inputs, missing fields, and error scenarios
4. Security Tests: Focus on URL validation, platform rejection, and security constraints
5. Edge Cases (Processing): Test unusual scenarios (empty meetings, very long transcripts, 
   special characters, concurrent requests, duplicate files)
6. Integration Tests: Test interaction with external services (Trello, Confluence, Graph API)
7. Error Recovery Tests: Test graceful degradation when external services fail
8. Performance Tests: Test with large files, long transcripts, multiple concurrent requests

OUTPUT FORMAT:
Please format your output as a Markdown table with the following columns:

| ID | Category | Test Case Description | Test Data/Input | Expected Result | Priority |

Priority levels: P0 (Critical - must work), P1 (Important), P2 (Nice to have)

EXAMPLE TEST CASES FOR REFERENCE:

| ID | Category | Test Case Description | Test Data/Input | Expected Result | Priority |
|----|----------|----------------------|-----------------|-----------------|----------|
| TC001 | Functional | Valid Teams URL processing | teams_url: "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc123", project_name: "TestProject" | 200 OK, summary returned with all fields populated | P0 |
| TC002 | Security | Reject Zoom URL | teams_url: "https://zoom.us/j/123456789", project_name: "TestProject" | 400 Bad Request, error: "Zoom is not supported. Only Microsoft Teams URLs are accepted" | P0 |
| TC003 | Validation | Missing required field (project_name) | teams_url: "https://teams.microsoft.com/l/meetup-join/...", project_name: null | 422 Validation Error, error: "project_name is required" | P0 |
| TC004 | Negative | Empty URL | teams_url: "", project_name: "TestProject" | 400 Bad Request, error: "URL is required" | P0 |
| TC005 | Edge Case | Duplicate file upload | Upload same file twice with same project_name | First: 200 OK, Second: Returns confirmation request with existing meeting info | P1 |
| TC006 | Integration | Trello sync failure | Valid request, but Trello API unavailable | 200 OK, summary saved locally, trello_board_url: null, log shows Trello sync failed | P1 |
| TC007 | Performance | Large audio file (400MB) | Audio file near size limit | 200 OK, successful processing within reasonable time (< 10 minutes) | P2 |
| TC008 | Edge Case | Meeting with no action items | Transcript with only discussion, no tasks | 200 OK, action_items: [], metadata includes "empty_meeting" flag | P2 |

ADDITIONAL INSTRUCTIONS:
- Include at least 3 test cases for URL validation (different rejected platforms)
- Include at least 2 test cases for duplicate detection
- Include at least 2 test cases for graceful degradation (external services down)
- Include at least 1 test case for SQL injection prevention
- Include at least 1 test case for XSS prevention
- For each negative test, specify the exact expected error message
- For each validation test, specify the expected HTTP status code

Please generate the test cases now.
```

---

## 📝 Example: Filled-In Prompt for Specific Feature

Here's an example of how to use the template for a specific feature:

### Feature: Teams Meeting URL Processor

```
Please act as a Senior QA Engineer with expertise in API testing, security validation, and 
edge case identification. I need you to generate a comprehensive set of test cases for a 
new feature in my Meeting Summarizer POC application.

FEATURE TO TEST:
Process a Microsoft Teams meeting URL to automatically download recordings, transcribe them, 
and generate AI-powered summaries with action items.

FEATURE SPECIFICATION:
Input: 
- POST request to /api/transcripts/process-teams-url
- Required fields: teams_url (string), project_name (string)
- Optional fields: meeting_title (string), skip_sync (boolean), analyze_project (boolean)

Output: 
- JSON object containing:
  - success: boolean
  - summary_id: string (UUID)
  - meeting_title: string
  - meeting_date: datetime
  - overall_summary: string
  - action_items: array of objects (description, owner, deadline, status, tags)
  - decisions: array of strings
  - risks: array of objects (description, severity)
  - action_items_count: integer
  - decisions_count: integer
  - risks_count: integer
  - trello_board_url: string (optional)
  - confluence_page_url: string (optional)

Expected Behavior:
1. Validate Teams URL (reject all non-Teams platforms)
2. Extract meeting ID from URL
3. Call Microsoft Graph API to get meeting details
4. Search SharePoint for recordings
5. Download recording files
6. Transcribe using Whisper model
7. Generate summary using GPT-3.5-turbo/GPT-4
8. Extract action items, decisions, and risks
9. Save to SQLite database
10. Sync to Trello (create board, lists, cards)
11. Sync to Confluence (create page)
12. Return complete summary data

[... rest of constraints and instructions remain the same ...]
```

---

## 🎯 Quick Fill Templates for Common Features

### Template 1: New API Endpoint

```
FEATURE TO TEST:
[Endpoint name and HTTP method, e.g., "GET /api/action-items/"]

Input: 
- HTTP [METHOD] request to [endpoint path]
- Query parameters: [list all query params with types]
- Headers: [list required headers]
- Body: [describe request body if applicable]

Output: 
- HTTP status code: [expected status]
- JSON response containing: [describe response structure]

Expected Behavior:
[Step-by-step description of what the endpoint does]
```

### Template 2: Data Processing Feature

```
FEATURE TO TEST:
[Processing feature name, e.g., "Action item status detection and migration"]

Input: 
- Raw transcript text containing: [describe input format]
- Configuration parameters: [list parameters]

Output: 
- Processed data structure: [describe output]
- Side effects: [database updates, file creation, etc.]

Expected Behavior:
[Step-by-step description of the processing logic]
```

### Template 3: Integration Feature

```
FEATURE TO TEST:
[Integration name, e.g., "Trello board synchronization"]

Input: 
- Meeting summary data: [describe structure]
- Project name: string
- Configuration: [API keys, credentials]

Output: 
- External system changes: [what gets created/updated]
- Updated internal data: [what gets stored locally]

Expected Behavior:
[Step-by-step description of the integration flow]
```

---

## 📊 Test Case Categories Explained

### 1. Functional Tests (Happy Path)
**Purpose:** Verify the feature works correctly with valid inputs
**Examples:**
- Valid Teams URL returns complete summary
- File upload processes successfully
- Summary retrieval returns correct data

### 2. Validation Tests
**Purpose:** Ensure all input parameters are properly validated
**Examples:**
- Missing required fields rejected (422)
- Invalid data types rejected (422)
- Out-of-range values rejected (400)

### 3. Negative Tests
**Purpose:** Test how the system handles invalid inputs and error conditions
**Examples:**
- Empty/null inputs rejected
- Malformed URLs rejected
- Invalid file types rejected

### 4. Security Tests
**Purpose:** Verify security constraints and protections
**Examples:**
- Only Teams URLs accepted (Zoom/Meet/etc. rejected)
- SQL injection attempts blocked
- XSS attempts sanitized
- Authentication required (if configured)

### 5. Edge Cases
**Purpose:** Test unusual or boundary scenarios
**Examples:**
- Empty meetings (no action items)
- Very long transcripts
- Special characters in text
- Duplicate file uploads
- Concurrent requests

### 6. Integration Tests
**Purpose:** Test interaction with external services
**Examples:**
- Trello sync creates cards correctly
- Confluence page created with proper formatting
- Graph API returns meeting details
- SharePoint downloads files

### 7. Error Recovery Tests
**Purpose:** Test graceful degradation when things go wrong
**Examples:**
- Trello unavailable → Continue without sync
- Confluence unavailable → Continue without storage
- AI API timeout → Return error gracefully
- Database locked → Retry logic works

### 8. Performance Tests
**Purpose:** Test system behavior under load
**Examples:**
- Large files (near size limit)
- Long processing times
- Multiple concurrent requests
- Database query performance

---

## 🔍 Critical Areas to Test

Based on the Meeting Summarizer POC architecture, always include tests for:

### ✅ Must Test (P0)
1. **URL Validation** - Only Teams URLs accepted
2. **Required Fields** - All required parameters validated
3. **Database Operations** - CRUD operations work correctly
4. **Error Codes** - Correct HTTP status codes returned
5. **Data Integrity** - Foreign keys and relationships maintained

### ⚠️ Should Test (P1)
6. **External Integrations** - Trello, Confluence sync
7. **Duplicate Detection** - File hash checking
8. **Status Management** - Action item status transitions
9. **Error Handling** - Graceful error messages
10. **Authentication** - Bearer token validation (if enabled)

### 💡 Nice to Test (P2)
11. **Performance** - Large file handling
12. **Concurrency** - Multiple simultaneous requests
13. **Multi-meeting Analysis** - Pattern detection
14. **Reminder System** - Email notifications
15. **Progress Tracking** - Real-time updates

---

## 📋 Test Case Template (Blank)

Copy and paste this table to start documenting test cases:

```markdown
| ID | Category | Test Case Description | Test Data/Input | Expected Result | Priority |
|----|----------|----------------------|-----------------|-----------------|----------|
| TC001 | Functional |  |  |  | P0 |
| TC002 | Validation |  |  |  | P0 |
| TC003 | Negative |  |  |  | P0 |
| TC004 | Security |  |  |  | P0 |
| TC005 | Edge Case |  |  |  | P1 |
| TC006 | Integration |  |  |  | P1 |
| TC007 | Error Recovery |  |  |  | P1 |
| TC008 | Performance |  |  |  | P2 |
```

---

## 🚀 Usage Instructions

### Step 1: Identify Your Feature
Clearly define what you want to test:
- Is it a new API endpoint?
- Is it a data processing feature?
- Is it an integration with external service?
- Is it a bug fix or enhancement?

### Step 2: Fill in the Template
Replace the bracketed sections with specific information:
- **Feature description**: One clear sentence
- **Input specification**: All parameters with types
- **Output specification**: Complete response structure
- **Expected behavior**: Step-by-step flow

### Step 3: Add Context
Include any special considerations:
- Dependencies on other features
- Configuration requirements
- Known limitations
- Performance expectations

### Step 4: Generate Test Cases
Use the filled template with an AI assistant or share with your QA team to generate comprehensive test cases.

### Step 5: Review and Refine
Ensure the generated test cases cover:
- ✅ All happy path scenarios
- ✅ All validation rules
- ✅ All error conditions
- ✅ All edge cases
- ✅ All integration points
- ✅ All security constraints

---

## 💡 Pro Tips

### For Better Test Case Generation:

1. **Be Specific**: Instead of "process URL", say "process Teams meeting URL to download recording and generate summary"

2. **Include Examples**: Provide sample inputs and outputs in the prompt

3. **Mention Constraints**: Always include system constraints (file size limits, allowed formats, etc.)

4. **Specify Error Messages**: Define exact error messages you expect for validation failures

5. **Consider User Flow**: Think about how users will actually use the feature

6. **Think About Failures**: What could go wrong? Network issues? Invalid data? External service down?

7. **Don't Forget Edge Cases**: Empty data, very large data, special characters, concurrent access

8. **Security First**: Always include security tests for new features

---

## 📖 Reference: Existing Test Coverage

Use these as examples when generating new test cases:

### Security Test Pattern
```
Test: Reject [Platform] URL
Input: teams_url: "https://[platform].com/meeting/123"
Expected: 400 Bad Request, error: "[Platform] is not supported. Only Microsoft Teams URLs are accepted"
```

### Validation Test Pattern
```
Test: Missing required field [field_name]
Input: All fields except [field_name]
Expected: 422 Validation Error, error: "[field_name] is required"
```

### Edge Case Test Pattern
```
Test: [Unusual scenario]
Input: [Describe unusual input]
Expected: [How system should handle it gracefully]
```

### Integration Test Pattern
```
Test: [Service] sync when [condition]
Input: Valid data + [service] [available/unavailable]
Expected: [Expected behavior with/without service]
```

---

## 🎓 Best Practices

### DO:
✅ Generate at least 20 test cases per feature
✅ Cover all input parameters
✅ Test all error conditions
✅ Include edge cases
✅ Specify exact expected results
✅ Assign priorities (P0/P1/P2)
✅ Use descriptive test case names
✅ Group by category

### DON'T:
❌ Skip negative tests
❌ Forget to test error messages
❌ Ignore edge cases
❌ Forget about security
❌ Skip integration testing
❌ Ignore performance implications
❌ Use vague descriptions

---

## 📊 Test Case Tracking

After generating test cases, track them:

```markdown
| Test ID | Status | Implemented | Automated | Last Run | Result |
|---------|--------|-------------|-----------|----------|--------|
| TC001 | ✅ Done | Yes | Yes | 2025-12-08 | Pass |
| TC002 | 🔄 In Progress | No | No | - | - |
| TC003 | ⏳ Pending | No | No | - | - |
```

---

## Summary

This prompt template helps you generate comprehensive test cases for any feature in the Meeting Summarizer POC application. By providing clear context, constraints, and examples, you ensure that all aspects of the feature are thoroughly tested.

**Key Points:**
- ✅ Customize the template for your specific feature
- ✅ Include all system constraints
- ✅ Request minimum 20 test cases
- ✅ Cover all categories (Functional, Validation, Negative, Security, Edge Cases, Integration, Error Recovery, Performance)
- ✅ Specify expected results including error messages
- ✅ Assign priorities
- ✅ Use the provided examples as reference

---

Last Updated: December 8, 2025
Project: Meeting Summarizer POC
Template Version: 1.0

