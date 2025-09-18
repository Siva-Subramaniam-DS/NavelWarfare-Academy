# Requirements Document

## Introduction

This feature involves updating the existing help command in the Discord tournament management bot to provide a more comprehensive, user-friendly, and organized command reference. The current help command provides basic information but lacks detailed descriptions, role-based filtering, and proper categorization of commands based on user permissions.

## Requirements

### Requirement 1

**User Story:** As a tournament participant, I want to see only the commands I have permission to use, so that I don't get confused by commands I cannot access.

#### Acceptance Criteria

1. WHEN a user without special roles runs `/help` THEN the system SHALL display only commands available to regular users
2. WHEN a user with Judge role runs `/help` THEN the system SHALL display commands available to judges and regular users
3. WHEN a user with Organizer role runs `/help` THEN the system SHALL display all available commands including administrative ones
4. WHEN a user with Bot Operator role runs `/help` THEN the system SHALL display all available commands including administrative ones

### Requirement 2

**User Story:** As a user, I want to see detailed descriptions and usage examples for each command, so that I can understand how to use them properly.

#### Acceptance Criteria

1. WHEN the help command is displayed THEN each command SHALL include a clear description of its purpose
2. WHEN the help command is displayed THEN commands with parameters SHALL include usage examples
3. WHEN the help command is displayed THEN role requirements SHALL be clearly indicated for restricted commands
4. WHEN the help command is displayed THEN commands SHALL be grouped by functionality for better organization

### Requirement 3

**User Story:** As a tournament organizer, I want to see administrative commands clearly separated from regular commands, so that I can quickly find the management tools I need.

#### Acceptance Criteria

1. WHEN an organizer views the help command THEN administrative commands SHALL be grouped in a separate section
2. WHEN an organizer views the help command THEN each administrative command SHALL clearly indicate required permissions
3. WHEN an organizer views the help command THEN the system SHALL highlight commands specific to event management

### Requirement 4

**User Story:** As a judge, I want to see judge-specific commands highlighted, so that I can quickly access the tools relevant to my role.

#### Acceptance Criteria

1. WHEN a judge views the help command THEN judge-specific commands SHALL be clearly identified
2. WHEN a judge views the help command THEN the system SHALL show commands for taking schedules and recording results
3. WHEN a judge views the help command THEN role-based permissions SHALL be clearly indicated

### Requirement 5

**User Story:** As any user, I want the help command to be visually appealing and easy to navigate, so that I can quickly find the information I need.

#### Acceptance Criteria

1. WHEN the help command is displayed THEN it SHALL use appropriate Discord embed formatting with colors and emojis
2. WHEN the help command is displayed THEN commands SHALL be organized in logical categories
3. WHEN the help command is displayed THEN the embed SHALL include proper branding and footer information
4. WHEN the help command is displayed THEN the response SHALL be sent as an ephemeral message to avoid channel clutter