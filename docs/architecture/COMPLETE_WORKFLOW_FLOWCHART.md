# Complete Project Workflow - Full Flowchart

## Overview
This document provides a comprehensive end-to-end flowchart of the entire Meeting Summarizer project, from user interaction through data processing to final storage and notifications.

---

## 🎯 Complete System Flowchart (Mermaid)

```mermaid
flowchart TB
    %% USER INTERACTION LAYER
    Start([User/Client]) --> Interface{Access Method?}
    Interface -->|Web UI| Frontend[Web Frontend<br/>localhost:8000]
    Interface -->|API Call| APIClient[API Client<br/>curl/Postman]
    Interface -->|CLI| CommandLine[Command Line<br/>scripts/main.py]
    
    Frontend --> UserAction{User Action?}
    APIClient --> UserAction
    CommandLine --> UserAction
    
    %% USER ACTIONS
    UserAction -->|Upload File| FileUpload[Upload File]
    UserAction -->|Teams URL| TeamsURL[Enter Teams URL]
    UserAction -->|SharePoint URL| SharePointURL[Enter SharePoint URL]
    UserAction -->|View Summary| ViewSummary[View Summary Request]
    UserAction -->|View Action Items| ViewActionItems[View Action Items Request]
    UserAction -->|View Projects| ViewProjects[View Projects Request]
    UserAction -->|Delete Meeting| DeleteMeeting[Delete Meeting Request]
    UserAction -->|Delete Project| DeleteProject[Delete Project Request]
    UserAction -->|Send Reminders| SendReminders[Trigger Reminders]
    
    %% AUTHENTICATION & ROUTING
    FileUpload --> Auth{Authentication<br/>Required?}
    TeamsURL --> Auth
    SharePointURL --> Auth
    ViewSummary --> Auth
    ViewActionItems --> Auth
    ViewProjects --> Auth
    DeleteMeeting --> Auth
    DeleteProject --> Auth
    SendReminders --> Auth
    
    Auth -->|Invalid Token| Error401[401 Unauthorized]
    Auth -->|Valid/Not Required| Router{Route to API Endpoint}
    
    %% API ENDPOINTS ROUTING
    Router -->|/api/transcripts/process| EP1[POST /api/transcripts/process]
    Router -->|/api/transcripts/process-teams-url| EP2[POST /api/transcripts/process-teams-url]
    Router -->|/api/transcripts/process-sharepoint-url| EP3[POST /api/transcripts/process-sharepoint-url]
    Router -->|/api/summaries/:id| EP4[GET /api/summaries/:id]
    Router -->|/api/summaries/project/:name| EP5[GET /api/summaries/project/:name]
    Router -->|/api/action-items/| EP6[GET /api/action-items/]
    Router -->|/api/projects/| EP7[GET /api/projects/]
    Router -->|/api/summaries/:id DELETE| EP8[DELETE /api/summaries/:id]
    Router -->|/api/projects/:name DELETE| EP9[DELETE /api/projects/:name]
    
    %% FILE UPLOAD FLOW (EP1)
    EP1 --> ValidateInput1[Validate Input<br/>- File present?<br/>- Project name?<br/>- Valid format?]
    ValidateInput1 -->|Invalid| Error422[422 Validation Error]
    ValidateInput1 -->|Valid| SanitizeInputs[Sanitize Inputs<br/>- Project name<br/>- Meeting title<br/>- Participants]
    
    SanitizeInputs --> ValidateFile[Validate File<br/>- Extension<br/>- MIME type<br/>- Size limit<br/>- Security check]
    ValidateFile -->|Invalid| Error400[400 Bad Request]
    ValidateFile -->|Valid| GenerateProcessID[Generate Process ID<br/>Initialize Progress Tracking]
    
    GenerateProcessID --> SaveTempFile[Save to Temporary File]
    SaveTempFile --> CalcHash[Calculate SHA-256 Hash]
    CalcHash --> CheckDuplicate{Duplicate<br/>File?}
    
    CheckDuplicate -->|Yes| CheckOldMeeting{Old Meeting<br/>Same Project?}
    CheckOldMeeting -->|Yes| CopyPermanent[Copy to Permanent Location]
    CopyPermanent --> ReturnConfirmation[Return Confirmation Request<br/>requires_confirmation: true]
    ReturnConfirmation --> WaitConfirm{User<br/>Confirms?}
    WaitConfirm -->|Reprocess| ProcessFileFlow
    WaitConfirm -->|Skip| ReturnExisting[Return Existing Meeting Info]
    
    CheckDuplicate -->|No| ProcessFileFlow[File Processing Flow]
    CheckOldMeeting -->|No - Different Project| ProcessFileFlow
    
    %% TEAMS URL FLOW (EP2)
    EP2 --> ValidateTeamsURL[Validate Teams URL<br/>CRITICAL: Teams Only!]
    ValidateTeamsURL -->|Invalid Format| Error400
    ValidateTeamsURL -->|Zoom/Meet/Webex| Error400Rejected[400 Bad Request<br/>"Platform not supported"]
    ValidateTeamsURL -->|Valid Teams URL| ExtractMeetingID[Extract Meeting ID<br/>from URL Pattern]
    
    ExtractMeetingID --> AuthGraph{Microsoft Graph<br/>Auth Available?}
    AuthGraph -->|No| Error500[500 Internal Error<br/>"Graph API not configured"]
    AuthGraph -->|Yes| GetAccessToken[Get Access Token<br/>via Client Credentials]
    
    GetAccessToken --> GetMeetingDetails[Graph API:<br/>GET /me/onlineMeetings/:id]
    GetMeetingDetails -->|Not Found| Error404[404 Meeting Not Found]
    GetMeetingDetails -->|Success| ExtractMetadata[Extract Meeting Metadata<br/>- Subject<br/>- Start/End Time<br/>- Participants]
    
    ExtractMetadata --> SearchRecordings[Search SharePoint<br/>for Recordings/Transcripts]
    SearchRecordings -->|None Found| Error404Recording[404 No Recordings]
    SearchRecordings -->|Multiple Found| ReturnSelection[Return Recording List<br/>Require User Selection]
    SearchRecordings -->|Single/Selected| DownloadFromSharePoint
    
    %% SHAREPOINT FLOW (EP3)
    EP3 --> ValidateSharePointURL[Validate Teams URL]
    ValidateSharePointURL -->|Invalid| Error400
    ValidateSharePointURL -->|Valid| ExtractIDs[Extract Meeting ID<br/>& User ID from URL]
    
    ExtractIDs --> SearchSharePoint[Search SharePoint<br/>- Recordings folder<br/>- Filter by meeting ID]
    SearchSharePoint -->|None Found| Error404Recording
    SearchSharePoint -->|Found| FilterSelection{User<br/>Selected Files?}
    
    FilterSelection -->|Yes| ApplyFilter[Filter by Selection]
    FilterSelection -->|No| UseAll[Use All Found]
    ApplyFilter --> DownloadFromSharePoint[Download Files from SharePoint]
    UseAll --> DownloadFromSharePoint
    
    DownloadFromSharePoint --> ValidateDownloadSize{File Size<br/>Valid?}
    ValidateDownloadSize -->|Too Large| Error400Size[400 File Too Large]
    ValidateDownloadSize -->|Valid| ProcessFileFlow
    
    %% FILE PROCESSING FLOW
    ProcessFileFlow --> UpdateProgress10[Update Progress: 10%<br/>File Validated]
    UpdateProgress10 --> DetectFileType{File Type?}
    
    DetectFileType -->|Audio| ProcessAudio[Process Audio File<br/>Extensions: .mp3, .wav, .m4a]
    DetectFileType -->|Video| ProcessVideo[Process Video File<br/>Extensions: .mp4, .avi, .mov]
    DetectFileType -->|Text| ProcessText[Process Text File<br/>Extensions: .txt, .json, .srt]
    
    ProcessAudio --> UpdateProgress30[Update Progress: 30%<br/>Processing Started]
    ProcessVideo --> UpdateProgress30
    ProcessText --> UpdateProgress30
    
    UpdateProgress30 --> MediaCheck{Media File?}
    MediaCheck -->|Yes - Audio/Video| LoadWhisper[Load Whisper Model<br/>base/small/medium]
    MediaCheck -->|No - Text| ReadText[Read Text Content<br/>Parse Format]
    
    LoadWhisper --> Transcribe[Transcribe with Whisper<br/>- Extract audio track<br/>- Generate transcript<br/>- Segment timestamps]
    Transcribe --> UpdateProgress50[Update Progress: 50%<br/>Transcription Complete]
    
    ReadText --> ParseFormat{Format?}
    ParseFormat -->|Plain Text| DirectUse[Use Directly]
    ParseFormat -->|JSON| ExtractJSON[Extract Text Field]
    ParseFormat -->|SRT/VTT| ExtractDialogue[Extract Dialogue]
    DirectUse --> UpdateProgress50
    ExtractJSON --> UpdateProgress50
    ExtractDialogue --> UpdateProgress50
    
    UpdateProgress50 --> ExtractMetadataFile[Extract Metadata<br/>- Date from filename/content<br/>- Participants<br/>- Duration]
    
    ExtractMetadataFile --> CreateTranscriptObj[Create MeetingTranscript Object<br/>- transcript_text<br/>- project_name<br/>- file_type<br/>- metadata]
    
    %% GENAI SUMMARIZATION
    CreateTranscriptObj --> UpdateProgress60[Update Progress: 60%<br/>Preparing Summarization]
    UpdateProgress60 --> BuildPrompt[Build Summarization Prompt<br/>DETAILED INSTRUCTIONS]
    
    BuildPrompt --> PromptStructure[Prompt Structure:<br/>1. System Instructions<br/>2. JSON Format Definition<br/>3. Critical Rules<br/>4. Examples<br/>5. Transcript Content]
    
    PromptStructure --> CriticalInstructions[Critical Instructions:<br/>- Extract ALL action items<br/>- Include completed tasks<br/>- Detect status keywords<br/>- Extract owner names<br/>- Identify deadlines<br/>- Tag dependencies<br/>- Extract decisions<br/>- Identify risks]
    
    CriticalInstructions --> CallOpenAI[Call OpenAI API<br/>POST /chat/completions]
    CallOpenAI --> OpenAIParams[Parameters:<br/>- Model: gpt-3.5-turbo/gpt-4<br/>- Temperature: 0.7<br/>- Max tokens: 4000<br/>- Response format: JSON]
    
    OpenAIParams --> APIResponse{API<br/>Success?}
    APIResponse -->|Fail| TryHuggingFace{HuggingFace<br/>Configured?}
    TryHuggingFace -->|Yes| CallHuggingFace[Call HuggingFace API]
    TryHuggingFace -->|No| Error500AI[500 AI Service Error]
    CallHuggingFace --> HFResponse{Success?}
    HFResponse -->|No| Error500AI
    HFResponse -->|Yes| ParseResponse
    
    APIResponse -->|Success| ParseResponse[Parse JSON Response<br/>Extract from markdown if needed]
    
    ParseResponse --> ExtractEntities[Extract Entities:<br/>- Action Items<br/>- Decisions<br/>- Risks<br/>- Topics<br/>- Summary]
    
    ExtractEntities --> UpdateProgress75[Update Progress: 75%<br/>Summary Generated]
    
    %% POST-PROCESSING
    UpdateProgress75 --> PostProcess[Post-Processing]
    
    PostProcess --> ValidateActionItems[Validate Action Items<br/>For Each Item:]
    ValidateActionItems --> OwnerValidation{Owner<br/>Valid?}
    
    OwnerValidation -->|Date Pattern| FixOwner[Set Owner: "Unassigned"]
    OwnerValidation -->|Placeholder| FixOwner
    OwnerValidation -->|Valid Name| StatusCheck{Status<br/>Valid?}
    FixOwner --> StatusCheck
    
    StatusCheck -->|Old Values| MigrateStatus[Migrate Status:<br/>- todo → PENDING<br/>- in_progress → DOING<br/>- completed → DONE]
    StatusCheck -->|Valid| KeywordCheck{Completion<br/>Keywords?}
    MigrateStatus --> KeywordCheck
    
    KeywordCheck -->|"completed", "done", etc.| ForceComplete[Force Status: DONE<br/>Clear Deadline]
    KeywordCheck -->|No Keywords| KeepStatus[Keep Status]
    ForceComplete --> NextItem
    KeepStatus --> NextItem
    
    NextItem --> MoreItems{More<br/>Items?}
    MoreItems -->|Yes| ValidateActionItems
    MoreItems -->|No| FallbackExtraction
    
    FallbackExtraction[Fallback Extraction<br/>Regex Pattern Matching]
    FallbackExtraction --> ScanTranscript[Scan Transcript for:<br/>- "completed: ..."<br/>- "done: ..."<br/>- Status indicators]
    
    ScanTranscript --> MatchItems[Match with Existing Items<br/>Fuzzy Matching]
    MatchItems --> AddMissed[Add Missed Completed Items]
    
    AddMissed --> CheckEmpty{Empty<br/>Meeting?}
    CheckEmpty -->|No Items/Decisions| MarkEmpty[Mark as Empty<br/>in Metadata]
    CheckEmpty -->|Has Content| HandleUnassigned{Unassigned<br/>Items?}
    MarkEmpty --> HandleUnassigned
    
    HandleUnassigned -->|Yes| AssignToOwner[Assign to Project Owner<br/>or Leave Unassigned]
    HandleUnassigned -->|No| CreateSummaryObj
    AssignToOwner --> SendAssignmentEmail{Owner Email<br/>Found?}
    SendAssignmentEmail -->|Yes| EmailAssignment[Send Assignment Email]
    SendAssignmentEmail -->|No| CreateSummaryObj
    EmailAssignment --> CreateSummaryObj
    
    CreateSummaryObj[Create MeetingSummary Object<br/>- All action items<br/>- All decisions<br/>- All risks<br/>- Overall summary<br/>- Metadata]
    
    %% DATA STORAGE
    CreateSummaryObj --> UpdateProgress80[Update Progress: 80%<br/>Saving Data]
    UpdateProgress80 --> SaveToDB[(Save to SQLite Database)]
    
    SaveToDB --> InsertMeeting[INSERT INTO meetings<br/>- id (UUID)<br/>- project_name<br/>- meeting_title<br/>- meeting_date<br/>- overall_summary<br/>- participants<br/>- tags<br/>- created_at]
    
    InsertMeeting --> InsertActionItems[INSERT INTO action_items<br/>For Each Action Item:<br/>- meeting_id<br/>- description<br/>- owner<br/>- deadline<br/>- status<br/>- dependencies<br/>- tags]
    
    InsertActionItems --> SaveToFiles[Save to File System<br/>data/:project/:date_time/]
    SaveToFiles --> SaveSummaryJSON[Save summary.json<br/>Complete MeetingSummary]
    SaveSummaryJSON --> SaveTranscriptJSON[Save transcript.json<br/>Complete MeetingTranscript]
    SaveTranscriptJSON --> CopyOriginal[Copy Original File<br/>Preserve for reference]
    
    CopyOriginal --> MarkProcessed[Mark File as Processed<br/>INSERT INTO processed_files<br/>- file_hash<br/>- project_name<br/>- meeting_id<br/>- processed_at]
    
    %% EXTERNAL INTEGRATIONS
    MarkProcessed --> CheckSkipSync{skip_sync<br/>Flag?}
    CheckSkipSync -->|Yes| SkipIntegrations[Skip External Integrations]
    CheckSkipSync -->|No| SyncIntegrations[External Integrations]
    
    SyncIntegrations --> UpdateProgress85[Update Progress: 85%<br/>Syncing Integrations]
    UpdateProgress85 --> TrelloSync{Trello<br/>Configured?}
    
    TrelloSync -->|Yes| TrelloFlow[Trello Sync Flow]
    TrelloSync -->|No| ConfluenceSync
    
    TrelloFlow --> GetBoard[Get/Create Trello Board<br/>Project Name as Board Name]
    GetBoard --> CheckBoardCache{Board ID<br/>in Cache?}
    CheckBoardCache -->|Yes| UseCached[Use Cached Board ID]
    CheckBoardCache -->|No| SearchBoard[Search Boards by Name]
    SearchBoard -->|Found| CacheBoard[Cache Board ID]
    SearchBoard -->|Not Found| CreateBoard[Create New Board<br/>with Project Name]
    CreateBoard --> CacheBoard
    UseCached --> GetLists
    CacheBoard --> GetLists
    
    GetLists[Get/Create Lists<br/>- To Do<br/>- Doing<br/>- Done<br/>- Pending]
    
    GetLists --> ProcessAILoop[For Each Action Item]
    ProcessAILoop --> MatchCard{Existing<br/>Card?}
    
    MatchCard -->|Yes - External ID| GetCard[Get Card by ID]
    MatchCard -->|Yes - Fuzzy Match| FuzzyMatch[Fuzzy Match<br/>Description + Owner]
    MatchCard -->|No| DetermineList
    
    GetCard --> DetermineList{Target List?}
    FuzzyMatch --> DetermineList
    
    DetermineList -->|DONE| DoneList[Done List]
    DetermineList -->|DOING| DoingList[Doing List]
    DetermineList -->|PENDING/NEW| ToDoList[To Do List]
    DetermineList -->|Overdue| PendingList[Pending List]
    
    DoneList --> CardAction{Card<br/>Exists?}
    DoingList --> CardAction
    ToDoList --> CardAction
    PendingList --> CardAction
    
    CardAction -->|Yes| MoveCard[Move Card to Target List]
    CardAction -->|No| CreateCard[Create Card<br/>- Title: Description<br/>- Description: Owner, Deadline<br/>- Labels: Tags]
    
    MoveCard --> UpdateDeadline{Status<br/>DONE?}
    CreateCard --> UpdateDeadline
    
    UpdateDeadline -->|Yes| ClearDeadline[Clear Due Date]
    UpdateDeadline -->|No| SetDeadline[Set Due Date]
    
    ClearDeadline --> StoreExternalID[Store external_id<br/>in Database]
    SetDeadline --> StoreExternalID
    
    StoreExternalID --> MoreAI{More<br/>Items?}
    MoreAI -->|Yes| ProcessAILoop
    MoreAI -->|No| UpdateDBSync[Update Database<br/>trello_synced = 1]
    
    UpdateDBSync --> ConfluenceSync{Confluence<br/>Configured?}
    
    ConfluenceSync -->|Yes| ConfluenceFlow[Confluence Sync Flow]
    ConfluenceSync -->|No| MultiMeetingCheck
    
    ConfluenceFlow --> GenerateHTML[Generate HTML Content<br/>- Meeting Header<br/>- Summary Section<br/>- Action Items Table<br/>- Decisions List<br/>- Risks List]
    
    GenerateHTML --> GetSpace{Space<br/>Exists?}
    GetSpace -->|No| CreateSpace[Create Space<br/>Space Key from Config]
    GetSpace -->|Yes| CheckPage
    CreateSpace --> CheckPage
    
    CheckPage{Page<br/>Exists?}
    CheckPage -->|Yes| UpdatePage[Update Existing Page]
    CheckPage -->|No| CreatePage[Create New Page<br/>Title: Date - Summary]
    
    UpdatePage --> SetLabels[Set Labels<br/>- Project Name<br/>- Tags]
    CreatePage --> SetLabels
    
    SetLabels --> GetPageURL[Get Page URL]
    GetPageURL --> StoreConfluenceURL[Store confluence_url<br/>in Metadata]
    
    StoreConfluenceURL --> UpdateDBConfluence[Update Database<br/>confluence_stored = 1]
    
    UpdateDBConfluence --> MultiMeetingCheck{Analyze<br/>Project?}
    SkipIntegrations --> MultiMeetingCheck
    
    MultiMeetingCheck -->|Yes| MultiMeetingAnalysis[Multi-Meeting Analysis]
    MultiMeetingCheck -->|No| UpdateProgress95
    
    MultiMeetingAnalysis --> GetProjectMeetings[Get All Project Meetings<br/>from Database]
    GetProjectMeetings --> AnalyzePatterns[Analyze Patterns:<br/>- Recurring topics<br/>- Action item trends<br/>- Decision patterns<br/>- Risk evolution]
    
    AnalyzePatterns --> GenerateInsights[Generate Insights<br/>- Progress tracking<br/>- Blockers<br/>- Recommendations]
    GenerateInsights --> StoreAnalysis[Store Analysis<br/>in Database/Files]
    
    StoreAnalysis --> UpdateProgress95[Update Progress: 95%<br/>Finalizing]
    
    %% RESPONSE PREPARATION
    UpdateProgress95 --> PrepareResponse[Prepare Response]
    PrepareResponse --> FormatResponse[Format Response:<br/>- success: true<br/>- summary_id<br/>- meeting_title<br/>- meeting_date<br/>- action_items_count<br/>- decisions_count<br/>- risks_count<br/>- trello_board_url<br/>- confluence_page_url]
    
    FormatResponse --> UpdateProgress100[Update Progress: 100%<br/>Complete]
    UpdateProgress100 --> Return200[Return 200 OK<br/>with Summary Data]
    
    %% RETRIEVAL FLOWS
    EP4 --> GetSummaryByID[Query Database<br/>SELECT * FROM meetings<br/>WHERE id = ?]
    GetSummaryByID -->|Not Found| Error404NotFound[404 Summary Not Found]
    GetSummaryByID -->|Found| GetAIForSummary[Get Action Items<br/>for Meeting]
    GetAIForSummary --> CheckFullDetails{full_details<br/>Parameter?}
    CheckFullDetails -->|Yes| IncludeAll[Include All Details]
    CheckFullDetails -->|No| SummaryOnly[Summary Only]
    IncludeAll --> GetTrelloURL
    SummaryOnly --> GetTrelloURL
    GetTrelloURL{Trello<br/>Synced?}
    GetTrelloURL -->|Yes| AddTrelloURL[Add Trello Board URL]
    GetTrelloURL -->|No| GetConfluenceURL
    AddTrelloURL --> GetConfluenceURL{Confluence<br/>Stored?}
    GetConfluenceURL -->|Yes| AddConfluenceURL[Add Confluence Page URL]
    GetConfluenceURL -->|No| ReturnSummaryData
    AddConfluenceURL --> ReturnSummaryData[Return Summary Data]
    
    EP5 --> GetProjectSummaries[Query Database<br/>SELECT * FROM meetings<br/>WHERE project_name = ?<br/>ORDER BY meeting_date DESC]
    GetProjectSummaries --> ReturnProjectList[Return List of Summaries]
    
    EP6 --> ParseFilters{Filter<br/>Parameters?}
    ParseFilters -->|owner| FilterByOwner[Filter by Owner]
    ParseFilters -->|status| FilterByStatus[Filter by Status]
    ParseFilters -->|project| FilterByProject[Filter by Project]
    ParseFilters -->|None| GetAll[Get All Action Items]
    FilterByOwner --> QueryAI
    FilterByStatus --> QueryAI
    FilterByProject --> QueryAI
    GetAll --> QueryAI
    QueryAI[Query Database<br/>SELECT * FROM action_items<br/>with filters]
    QueryAI --> ReturnAIList[Return Action Items List]
    
    EP7 --> ScanDataDir[Scan Data Directory<br/>List Project Folders]
    ScanDataDir --> CountMeetings[For Each Project:<br/>Count Meetings]
    CountMeetings --> GetLatestDate[Get Latest Meeting Date]
    GetLatestDate --> BuildProjectList[Build Project List:<br/>- name<br/>- meeting_count<br/>- latest_meeting_date]
    BuildProjectList --> ReturnProjectsList[Return Projects List]
    
    %% DELETE FLOWS
    EP8 --> DeleteSummaryDB[DELETE FROM meetings<br/>WHERE id = ?]
    DeleteSummaryDB --> DeleteAIDB[DELETE FROM action_items<br/>WHERE meeting_id = ?]
    DeleteAIDB --> DeleteFiles[Delete File System Files<br/>data/:project/:date_time/]
    DeleteFiles --> DeleteProcessed[DELETE FROM processed_files<br/>WHERE meeting_id = ?]
    DeleteProcessed --> Return200Delete[Return 200 OK<br/>Deleted Successfully]
    
    EP9 --> GetProjectMeetingsDelete[Get All Meeting IDs<br/>for Project]
    GetProjectMeetingsDelete --> DeleteAllMeetings[Delete All Meetings<br/>Loop through IDs]
    DeleteAllMeetings --> ArchiveTrello{Trello<br/>Board Exists?}
    ArchiveTrello -->|Yes| ArchiveBoard[Archive/Delete<br/>Trello Board]
    ArchiveTrello -->|No| DeleteConfluence
    ArchiveBoard --> DeleteConfluence{Confluence<br/>Pages Exist?}
    DeleteConfluence -->|Yes| DeletePages[Delete Confluence Pages]
    DeleteConfluence -->|No| DeleteProjectDir
    DeletePages --> DeleteProjectDir[Delete Project Directory<br/>data/:project/]
    DeleteProjectDir --> Return200DeleteProject[Return 200 OK<br/>Project Deleted]
    
    %% BACKGROUND PROCESSES
    BGScheduler([Background Scheduler<br/>Every Hour]) --> CheckReminders[Check Pending Reminders<br/>Query action_items<br/>WHERE deadline BETWEEN<br/>NOW and NOW+24h]
    
    CheckReminders --> SyncTrelloDeadlines[Sync Deadlines from Trello<br/>Update Database]
    SyncTrelloDeadlines --> FilterPendingReminders[Filter Pending Items:<br/>- Status: NEW/PENDING/DOING<br/>- Not blocked<br/>- Deadline in window]
    
    FilterPendingReminders --> ReminderLoop[For Each Item]
    ReminderLoop --> GetOwnerEmail[Get Owner Email<br/>from email_mappings]
    GetOwnerEmail --> EmailFound{Email<br/>Found?}
    
    EmailFound -->|No| TrelloComment
    EmailFound -->|Yes| TrySMTP{SMTP<br/>Configured?}
    
    TrySMTP -->|Yes| SendSMTP[Send Email via SMTP<br/>smtplib]
    TrySMTP -->|No| TryGraphAPI
    
    SendSMTP -->|Success| LogReminderSent[Log: Reminder Sent]
    SendSMTP -->|Fail| TryGraphAPI{Graph API<br/>Configured?}
    
    TryGraphAPI -->|Yes| GetGraphToken[Get Access Token<br/>Refresh Token Flow]
    TryGraphAPI -->|No| TrelloComment
    
    GetGraphToken --> SendGraphEmail[Send Email via Graph API<br/>POST /me/sendMail]
    SendGraphEmail -->|Success| LogReminderSent
    SendGraphEmail -->|Fail| TrelloComment{Trello Card<br/>Exists?}
    
    TrelloComment -->|Yes| AddTrelloComment[Add Comment to Card<br/>"Reminder: Due in X hours"]
    TrelloComment -->|No| LogReminderSkipped[Log: Reminder Skipped]
    
    AddTrelloComment --> LogReminderSent
    LogReminderSent --> MoreReminders{More<br/>Items?}
    LogReminderSkipped --> MoreReminders
    MoreReminders -->|Yes| ReminderLoop
    MoreReminders -->|No| LogResults[Log Results:<br/>- Total checked<br/>- Reminders sent<br/>- Reminders failed]
    
    %% END NODES
    Return200 --> End([Response to Client])
    ReturnSummaryData --> End
    ReturnProjectList --> End
    ReturnAIList --> End
    ReturnProjectsList --> End
    Return200Delete --> End
    Return200DeleteProject --> End
    ReturnExisting --> End
    ReturnSelection --> End
    LogResults --> SchedulerEnd([Next Scheduled Run])
    
    %% ERROR NODES
    Error401 --> End
    Error400 --> End
    Error400Rejected --> End
    Error400Size --> End
    Error422 --> End
    Error404 --> End
    Error404NotFound --> End
    Error404Recording --> End
    Error500 --> End
    Error500AI --> End
    
    %% STYLING
    classDef userLayer fill:#90EE90,stroke:#333,stroke-width:2px
    classDef apiLayer fill:#87CEEB,stroke:#333,stroke-width:2px
    classDef processingLayer fill:#FFD700,stroke:#333,stroke-width:2px
    classDef aiLayer fill:#FF69B4,stroke:#333,stroke-width:2px
    classDef storageLayer fill:#FF6347,stroke:#333,stroke-width:2px
    classDef integrationLayer fill:#9370DB,stroke:#333,stroke-width:2px
    classDef errorLayer fill:#FF6B6B,stroke:#333,stroke-width:2px
    classDef backgroundLayer fill:#20B2AA,stroke:#333,stroke-width:2px
    
    class Start,Frontend,APIClient,CommandLine,End userLayer
    class EP1,EP2,EP3,EP4,EP5,EP6,EP7,EP8,EP9,Router apiLayer
    class ProcessFileFlow,DetectFileType,Transcribe,ReadText,ExtractMetadataFile processingLayer
    class BuildPrompt,CallOpenAI,ParseResponse,ExtractEntities,PostProcess aiLayer
    class SaveToDB,InsertMeeting,InsertActionItems,SaveToFiles,MarkProcessed storageLayer
    class TrelloFlow,ConfluenceFlow,GetBoard,CreateCard,CreatePage integrationLayer
    class Error401,Error400,Error400Rejected,Error400Size,Error422,Error404,Error404NotFound,Error404Recording,Error500,Error500AI errorLayer
    class BGScheduler,CheckReminders,ReminderLoop,SendSMTP,SendGraphEmail backgroundLayer
```

---

## 📊 System Architecture Overview

### Layer Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│                    1. USER INTERACTION LAYER                 │
│  - Web Frontend (HTML/CSS/JavaScript)                       │
│  - API Clients (curl, Postman, Python requests)             │
│  - CLI Scripts (command line interface)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    2. API ROUTING LAYER                      │
│  - FastAPI Application (backend/main.py)                    │
│  - Authentication Middleware                                 │
│  - CORS & Security Headers                                  │
│  - API Endpoints (backend/api/)                             │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    3. VALIDATION LAYER                       │
│  - Input Sanitization (security.py)                         │
│  - File Validation                                          │
│  - URL Validation (Teams Only!)                             │
│  - Duplicate Detection                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    4. PROCESSING LAYER                       │
│  - File Type Detection                                      │
│  - Transcription (Whisper Model)                            │
│  - Text Parsing                                             │
│  - Metadata Extraction                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    5. AI PROCESSING LAYER                    │
│  - Prompt Engineering                                       │
│  - OpenAI API Calls (GPT-3.5/GPT-4)                        │
│  - Response Parsing                                         │
│  - Entity Extraction (Action Items, Decisions, Risks)      │
│  - Post-Processing & Validation                             │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    6. DATA STORAGE LAYER                     │
│  - SQLite Database (meetings, action_items, projects)       │
│  - File System (JSON files, original files)                 │
│  - Hash Tracking (processed_files)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    7. INTEGRATION LAYER                      │
│  - Trello Sync (Board creation, Card management)            │
│  - Confluence Sync (Page creation, HTML formatting)         │
│  - SharePoint Access (File downloads)                       │
│  - Microsoft Graph API (Meeting details, Email)             │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    8. RESPONSE LAYER                         │
│  - Format JSON Response                                     │
│  - Include External URLs                                    │
│  - Return to Client                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 9. BACKGROUND PROCESSES LAYER                │
│  - Scheduler (APScheduler)                                  │
│  - Reminder System (Hourly checks)                          │
│  - Email Notifications (SMTP/Graph API)                     │
│  - Overdue Task Detection                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Diagram

```
[USER] → [FRONTEND] → [API] → [VALIDATION]
                                    ↓
                              [PROCESSING]
                                    ↓
                            [AI PROCESSING]
                                    ↓
                         [DATA STORAGE] ←→ [DATABASE]
                                    ↓
                            [INTEGRATIONS]
                              ↓         ↓
                        [TRELLO]  [CONFLUENCE]
                                    ↓
                              [RESPONSE]
                                    ↓
                              [FRONTEND]
                                    ↓
                               [USER]

[SCHEDULER] → [CHECK REMINDERS] → [SEND EMAILS] → [LOG RESULTS]
```

---

## 🎯 Critical Workflows

### 1. File Upload → Summary Generation

```
Upload File
  → Validate (security, format, size)
  → Check Duplicate (SHA-256 hash)
  → Process File (transcribe if audio/video)
  → Call AI (GPT for summarization)
  → Extract Entities (action items, decisions, risks)
  → Post-Process (validate owners, statuses)
  → Save Database (meetings, action_items)
  → Save Files (summary.json, transcript.json)
  → Sync Trello (create cards)
  → Sync Confluence (create page)
  → Return Response (with URLs)
```

### 2. Teams URL → Recording Download → Processing

```
Teams URL
  → Validate (Teams only - reject Zoom/Meet/etc.)
  → Extract Meeting ID
  → Graph API (get meeting details)
  → Search SharePoint (find recordings)
  → Download Files
  → Process (same as file upload flow)
```

### 3. Reminder System (Background)

```
Every Hour:
  → Query action_items (due within 24h)
  → For each item:
      → Get owner email
      → Try SMTP email
      → If fail → Try Graph API email
      → If fail → Add Trello comment
      → If fail → Skip
  → Log results (sent/failed counts)
```

### 4. Project Deletion

```
Delete Project
  → Get all meeting IDs
  → For each meeting:
      → Delete from database
      → Delete files
  → Archive Trello board
  → Delete Confluence pages
  → Delete project directory
  → Return success
```

---

## 🔒 Security Checkpoints

1. **Authentication**: Bearer token validation
2. **Input Sanitization**: Clean all user inputs
3. **File Validation**: Extension, MIME type, size
4. **URL Validation**: Only Microsoft Teams URLs
5. **SQL Injection Prevention**: Parameterized queries
6. **XSS Prevention**: Escaped output
7. **Path Traversal Prevention**: Validated paths

---

## 📁 File Locations

| Component | File Path |
|-----------|-----------|
| **Main App** | `backend/main.py` |
| **API Endpoints** | `backend/api/*.py` |
| **Transcription** | `backend/meeting_summarizer/core/transcript_processor.py` |
| **Summarization** | `backend/meeting_summarizer/core/summarizer.py` |
| **Storage** | `backend/meeting_summarizer/core/storage.py` |
| **Trello** | `backend/meeting_summarizer/integrations/action_item_manager.py` |
| **Confluence** | `backend/meeting_summarizer/integrations/knowledge_base.py` |
| **Security** | `backend/security.py` |
| **Frontend** | `frontend/templates/index.html`, `frontend/static/app.js` |

---

## 📊 Database Schema

```sql
meetings
  - id (UUID)
  - project_name
  - meeting_title
  - meeting_date
  - overall_summary
  - participants (JSON)
  - tags (JSON)
  - created_at
  - updated_at

action_items
  - id (UUID)
  - meeting_id (FK)
  - description
  - owner
  - deadline
  - status (ENUM)
  - dependencies (JSON)
  - tags (JSON)
  - external_id (Trello card ID)

processed_files
  - file_hash (SHA-256)
  - project_name
  - meeting_id (FK)
  - trello_synced (BOOLEAN)
  - confluence_stored (BOOLEAN)
  - processed_at

email_mappings
  - owner_name
  - email_address
```

---

## 🚀 Performance Optimizations

1. **Async Processing**: Long operations run asynchronously
2. **Progress Tracking**: Real-time updates via polling
3. **Caching**: Trello board IDs cached in memory
4. **Batch Operations**: Multiple cards created together
5. **Connection Pooling**: Database connections reused
6. **Lazy Loading**: Whisper model loaded on demand

---

Last Updated: December 8, 2025
Project: Meeting Summarizer POC
Total Flows: 9 major workflows
Total Endpoints: 15+ API endpoints


