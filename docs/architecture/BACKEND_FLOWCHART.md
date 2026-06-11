# Backend Flowchart - Mermaid Diagram

```mermaid
flowchart TB
    Start([Client Request]) --> Auth{Authentication<br/>Bearer Token?}
    Auth -->|Valid/Not Required| Route{API Endpoint}
    Auth -->|Invalid| Error1[Return 401 Unauthorized]
    
    Route -->|/api/transcripts/process| UploadFlow[File Upload Flow]
    Route -->|/api/process-teams-url| TeamsURLFlow[Teams URL Flow]
    Route -->|/api/transcripts/process-sharepoint-url| SharePointFlow[SharePoint Flow]
    Route -->|/api/summaries/*| SummaryFlow[Summary Retrieval]
    Route -->|/api/action-items/*| ActionItemFlow[Action Items]
    Route -->|/api/projects/*| ProjectFlow[Projects]
    
    %% File Upload Flow
    UploadFlow --> ValidateFile[Validate File<br/>- File type<br/>- File size<br/>- Security checks]
    ValidateFile -->|Invalid| Error2[Return 400 Bad Request]
    ValidateFile -->|Valid| SaveTemp[Save to Temp File]
    SaveTemp --> CheckDuplicate{Check Duplicate<br/>File Hash?}
    CheckDuplicate -->|Duplicate| ConfirmOld{Old Meeting?<br/>Requires Confirmation}
    CheckDuplicate -->|New| ProcessFile[Process File]
    ConfirmOld -->|Yes| ReturnConfirm[Return Confirmation Request]
    ConfirmOld -->|No| ProcessFile
    
    %% Teams URL Flow
    TeamsURLFlow --> ValidateURL[Validate Teams URL<br/>- Teams only<br/>- Format check]
    ValidateURL -->|Invalid| Error3[Return 400 Bad Request]
    ValidateURL -->|Valid| ExtractMeetingID[Extract Meeting ID<br/>from URL]
    ExtractMeetingID --> GetMeetingDetails[Get Meeting Details<br/>via Graph API]
    GetMeetingDetails --> SearchRecordings[Search Recordings<br/>in SharePoint]
    SearchRecordings -->|Multiple Found| ShowSelection[Return Recordings List<br/>Requires Selection]
    SearchRecordings -->|Single/Selected| DownloadFiles[Download Files]
    
    %% SharePoint Flow
    SharePointFlow --> ValidateURL2[Validate Teams URL]
    ValidateURL2 --> ExtractIDs[Extract Meeting & User IDs]
    ExtractIDs --> SearchSharePoint[Search SharePoint<br/>for Recordings/Transcripts]
    SearchSharePoint --> FilterFiles[Filter by Selection<br/>if provided]
    FilterFiles --> DownloadFiles
    
    %% Download and Process
    DownloadFiles --> ValidateSize{File Size<br/>Valid?}
    ValidateSize -->|Too Large| Error4[Return 400<br/>File Too Large]
    ValidateSize -->|Valid| ProcessFile
    
    %% Core Processing Pipeline
    ProcessFile --> DetectType{File Type?}
    DetectType -->|Audio/Video| Transcribe[Transcribe Audio<br/>Whisper Model]
    DetectType -->|Text| ReadText[Read Text File]
    Transcribe --> GetTranscript[Get Transcript Text]
    ReadText --> GetTranscript
    
    GetTranscript --> GenerateSummary[Generate Summary<br/>via LLM]
    GenerateSummary --> ExtractEntities[Extract Entities<br/>- Action Items<br/>- Decisions<br/>- Risks<br/>- Participants]
    
    ExtractEntities --> StoreDB[(Store in SQLite<br/>Database)]
    StoreDB --> CheckEmpty{Empty<br/>Meeting?}
    CheckEmpty -->|Yes| MarkEmpty[Mark as Empty<br/>in Metadata]
    CheckEmpty -->|No| SyncIntegrations[Sync to Integrations]
    
    %% Integration Sync
    SyncIntegrations --> SyncTrello{Trello<br/>Sync?}
    SyncTrello -->|Yes| CreateBoard[Create/Get Trello Board]
    CreateBoard --> CreateLists[Create Lists<br/>To Do, Doing, Done]
    CreateLists --> CreateCards[Create Action Item Cards]
    CreateCards --> AssignCards[Assign to Owners]
    AssignCards --> SendAssignmentReminder{Assignment<br/>Reminder?}
    SendAssignmentReminder -->|Yes| ReminderFlow[Send Reminder]
    
    SyncTrello -->|No/Skip| SyncConfluence{Confluence<br/>Sync?}
    SyncConfluence -->|Yes| CreatePage[Create Confluence Page]
    CreatePage --> FormatContent[Format Summary Content<br/>- Title<br/>- Summary<br/>- Action Items<br/>- Decisions<br/>- Risks]
    FormatContent --> StorePage[Store Page URL<br/>in Metadata]
    
    SyncConfluence -->|No/Skip| MultiMeeting{Multi-Meeting<br/>Analysis?}
    MultiMeeting -->|Yes| AnalyzeProject[Analyze Project<br/>Across Meetings]
    MultiMeeting -->|No| ReturnResponse[Return Response]
    AnalyzeProject --> ReturnResponse
    
    %% Summary Retrieval Flow
    SummaryFlow --> GetSummary[Get Summary from DB]
    GetSummary -->|Found| ReturnSummary[Return Summary Data]
    GetSummary -->|Not Found| Error5[Return 404]
    
    %% Action Items Flow
    ActionItemFlow --> FilterAI{Filter<br/>Parameters?}
    FilterAI -->|Owner| FilterByOwner[Filter by Owner]
    FilterAI -->|Status| FilterByStatus[Filter by Status]
    FilterAI -->|Project| FilterByProject[Filter by Project]
    FilterByOwner --> GetAIs[Get Action Items from DB]
    FilterByStatus --> GetAIs
    FilterByProject --> GetAIs
    GetAIs --> ReturnAIs[Return Action Items]
    
    %% Project Flow
    ProjectFlow --> ProjectOp{Operation?}
    ProjectOp -->|GET| ListProjects[List All Projects<br/>from DB]
    ProjectOp -->|POST| CreateProject[Create New Project]
    ProjectOp -->|DELETE| DeleteProject[Delete Project<br/>- Archive Trello<br/>- Delete Confluence<br/>- Clean DB]
    ProjectOp -->|Extract Emails| ExtractEmails[Extract Emails<br/>from Meetings]
    ListProjects --> ReturnProjects[Return Projects]
    CreateProject --> ReturnProjects
    DeleteProject --> ReturnProjects
    ExtractEmails --> ReturnProjects
    
    %% Reminder System Flow
    ReminderFlow --> CheckReminders[Check Pending Reminders<br/>12-24 hours before deadline]
    CheckReminders --> GetItems[Get Action Items<br/>from DB]
    GetItems --> SyncDeadlines[Sync Deadlines<br/>from Trello]
    SyncDeadlines --> FilterPending[Filter Pending<br/>12-24h window]
    FilterPending --> SendReminder{Send<br/>Reminder}
    
    SendReminder --> TrySMTP{SMTP<br/>Configured?}
    TrySMTP -->|Yes| SendEmailSMTP[Send Email via SMTP]
    TrySMTP -->|No| TryGraph{Graph API<br/>Configured?}
    TryGraph -->|Yes| GetToken[Get Access Token<br/>via Refresh Token]
    GetToken --> SendEmailGraph[Send Email via<br/>Graph API /me/sendMail]
    TryGraph -->|No| TryTrello{Trello<br/>Card Exists?}
    TryTrello -->|Yes| AddComment[Add Trello Comment]
    TryTrello -->|No| SkipReminder[Skip Reminder]
    
    SendEmailSMTP -->|Success| ReminderSent[Reminder Sent]
    SendEmailSMTP -->|Fail| TryGraph
    SendEmailGraph -->|Success| ReminderSent
    SendEmailGraph -->|Fail| TryTrello
    AddComment --> ReminderSent
    SkipReminder --> ReminderSent
    
    %% Assignment Reminder Flow
    SendAssignmentReminder -->|New Task| CheckEmail{Owner Email<br/>Found?}
    CheckEmail -->|Yes| SendAssignmentEmail[Send Assignment Email<br/>via SMTP/Graph API]
    CheckEmail -->|No| AddTrelloComment[Add Trello Comment]
    SendAssignmentEmail --> AssignmentSent[Assignment Reminder Sent]
    AddTrelloComment --> AssignmentSent
    
    %% Return Response
    ReturnResponse --> FormatResponse[Format Response<br/>- Summary ID<br/>- Process ID<br/>- Status]
    FormatResponse --> UpdateProgress[Update Progress<br/>Tracking]
    UpdateProgress --> End([Return Response to Client])
    
    ReturnSummary --> End
    ReturnAIs --> End
    ReturnProjects --> End
    ReminderSent --> End
    AssignmentSent --> End
    
    %% Error Handling
    Error1 --> End
    Error2 --> End
    Error3 --> End
    Error4 --> End
    Error5 --> End
    
    %% Styling
    classDef startEnd fill:#90EE90,stroke:#333,stroke-width:2px
    classDef process fill:#87CEEB,stroke:#333,stroke-width:2px
    classDef decision fill:#FFD700,stroke:#333,stroke-width:2px
    classDef database fill:#FF6347,stroke:#333,stroke-width:2px
    classDef integration fill:#9370DB,stroke:#333,stroke-width:2px
    classDef error fill:#FF6B6B,stroke:#333,stroke-width:2px
    
    class Start,End startEnd
    class ProcessFile,Transcribe,GenerateSummary,ExtractEntities,CreatePage,FormatContent process
    class Auth,Route,CheckDuplicate,ConfirmOld,DetectType,CheckEmpty,SyncTrello,SyncConfluence,MultiMeeting,FilterAI,ProjectOp,TrySMTP,TryGraph,TryTrello,CheckEmail decision
    class StoreDB,GetSummary,GetAIs,GetItems database
    class CreateBoard,CreateCards,CreatePage,SendEmailSMTP,SendEmailGraph,AddComment integration
    class Error1,Error2,Error3,Error4,Error5 error
```

## Backend Architecture Overview

### Main Components

1. **API Layer** (`backend/api/`)
   - `transcripts.py` - File upload and processing endpoints
   - `summaries.py` - Summary retrieval endpoints
   - `action_items.py` - Action item management endpoints
   - `projects.py` - Project management endpoints

2. **Core Processing** (`backend/meeting_summarizer/core/`)
   - `transcript_processor.py` - Audio/video transcription
   - `summarizer.py` - LLM-based summary generation
   - `storage.py` - SQLite database operations

3. **Integrations** (`backend/meeting_summarizer/integrations/`)
   - `action_item_manager.py` - Trello integration & reminders
   - `knowledge_base.py` - Confluence integration
   - `teams_integration.py` - Microsoft Teams API
   - `sharepoint_download.py` - SharePoint file downloads

4. **Security** (`backend/security.py`)
   - Bearer token authentication
   - File validation
   - Input sanitization

### Key Flows

#### 1. File Upload Flow
- File validation (type, size, security)
- Duplicate detection via file hash
- Transcription (if audio/video)
- Summary generation via LLM
- Entity extraction (action items, decisions, risks)
- Database storage
- Integration sync (Trello, Confluence)

#### 2. Teams URL Flow
- URL validation (Teams only)
- Meeting ID extraction
- Graph API meeting details
- SharePoint recording search
- File download and processing

#### 3. Reminder System Flow
- Check pending reminders (12-24h window)
- Sync deadlines from Trello
- Send reminders via:
  - SMTP (priority 1)
  - Graph API (priority 2)
  - Trello comments (fallback)

#### 4. Integration Sync Flow
- Trello: Create board → Lists → Cards → Assignments
- Confluence: Create page → Format content → Store URL
- Multi-meeting analysis (optional)

### Database Schema

- **meetings** - Meeting summaries
- **action_items** - Action items with deadlines
- **projects** - Project metadata
- **processed_files** - File hash tracking
- **email_mappings** - Owner email mappings

### Authentication Flow

- Bearer token validation (if configured)
- Public endpoints: File upload, processing
- Protected endpoints: Summaries, action items, projects

