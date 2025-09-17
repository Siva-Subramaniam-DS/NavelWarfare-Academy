# Requirements Document

## Introduction

This feature focuses on managing Discord channel IDs for the tournament system, specifically updating the attendance, results, and schedule channel IDs while removing transcript channel functionality. The system currently uses hardcoded channel IDs that need to be updated and the transcript channel functionality needs to be removed entirely.

## Requirements

### Requirement 1

**User Story:** As a tournament administrator, I want to update the channel IDs for attendance, results, and schedule channels, so that the bot directs messages to the correct Discord channels.

#### Acceptance Criteria

1. WHEN the system initializes THEN the bot SHALL use the new channel ID 1378979992641339403 for staff attendance
2. WHEN the system initializes THEN the bot SHALL use the new channel ID 1281967638360359067 for results
3. WHEN the system initializes THEN the bot SHALL use the new channel ID 1281967703506026538 for schedule
4. WHEN attendance tracking occurs THEN messages SHALL be sent to the updated attendance channel
5. WHEN results are posted THEN messages SHALL be sent to the updated results channel
6. WHEN schedules are created THEN messages SHALL be sent to the updated schedule channel

### Requirement 2

**User Story:** As a tournament administrator, I want to remove transcript channel functionality from the system, so that the bot no longer attempts to use or reference transcript channels.

#### Acceptance Criteria

1. WHEN the system initializes THEN the bot SHALL NOT include transcript channel ID in the CHANNEL_IDS configuration
2. WHEN any bot functionality executes THEN the system SHALL NOT attempt to send messages to transcript channels
3. WHEN the code is reviewed THEN there SHALL be no references to transcript channel functionality
4. WHEN the bot processes commands THEN it SHALL NOT create or manage transcript channels
5. IF any existing code references transcript channels THEN those references SHALL be removed or commented out

### Requirement 3

**User Story:** As a developer, I want the channel ID configuration to be easily maintainable, so that future channel updates can be made efficiently.

#### Acceptance Criteria

1. WHEN channel IDs are defined THEN they SHALL be stored in a centralized configuration structure
2. WHEN the configuration is updated THEN the changes SHALL be reflected across all bot functionality
3. WHEN reviewing the code THEN the channel ID mapping SHALL be clearly documented
4. IF channel IDs need to be changed in the future THEN only the configuration section SHALL require modification