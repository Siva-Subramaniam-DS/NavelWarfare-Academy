# Design Document

## Overview

The updated help command will provide a role-based, comprehensive command reference system for the Discord tournament management bot. The design focuses on creating a user-friendly interface that adapts to user permissions and provides detailed information about available commands.

## Architecture

### Role Detection System
The help command will implement a role detection mechanism that checks the user's Discord roles against predefined role IDs:
- `ROLE_IDS["organizer"]` - Full administrative access
- `ROLE_IDS["bot_op"]` - Bot operator permissions  
- `ROLE_IDS["judge"]` - Judge-specific permissions
- Regular users - Basic command access

### Command Categorization
Commands will be organized into logical categories:
1. **System Commands** - Basic bot functionality (`/help`, `/rules`)
2. **Event Management** - Tournament event operations (`/event-create`, `/event-result`, `/event-delete`)
3. **Utility Commands** - Helper tools (`/team_balance`, `/time`, `/choose`)
4. **Judge Commands** - Judge-specific functionality (schedule taking, result recording)

## Components and Interfaces

### Main Help Command Function
```python
@tree.command(name="help", description="Show available commands based on your permissions")
async def help_command(interaction: discord.Interaction):
```

### Role Permission Checker
```python
def get_user_permission_level(user_roles) -> str:
    # Returns: "organizer", "bot_op", "judge", or "user"
```

### Command Data Structure
```python
COMMAND_DATA = {
    "system": {
        "title": "⚙️ System Commands",
        "commands": [
            {
                "name": "/help",
                "description": "Display this command guide",
                "usage": "/help",
                "permissions": "everyone"
            },
            # ... more commands
        ]
    },
    # ... more categories
}
```

### Embed Builder
```python
def build_help_embed(permission_level: str) -> discord.Embed:
    # Builds role-appropriate embed with filtered commands
```

## Data Models

### Command Information Model
```python
@dataclass
class CommandInfo:
    name: str
    description: str
    usage: str
    permissions: str
    category: str
    examples: Optional[List[str]] = None
```

### Permission Levels
```python
class PermissionLevel(Enum):
    USER = "user"
    JUDGE = "judge"
    BOT_OP = "bot_op"
    ORGANIZER = "organizer"
```

## Error Handling

### Permission Detection Errors
- If role detection fails, default to basic user permissions
- Log permission detection errors for debugging
- Gracefully handle missing role configurations

### Embed Creation Errors
- Implement fallback text-based help if embed creation fails
- Handle Discord embed size limitations by truncating content appropriately
- Provide error messages for malformed command data

### Discord API Errors
- Handle interaction response timeouts
- Implement retry logic for failed message sends
- Provide user-friendly error messages for API failures

## Testing Strategy

### Unit Tests
1. **Role Detection Tests**
   - Test permission level detection for each role type
   - Test fallback behavior for users without special roles
   - Test handling of multiple roles

2. **Command Filtering Tests**
   - Verify correct commands are shown for each permission level
   - Test command categorization logic
   - Validate command data structure integrity

3. **Embed Generation Tests**
   - Test embed creation for each permission level
   - Verify proper formatting and content
   - Test handling of edge cases (empty categories, long descriptions)

### Integration Tests
1. **Discord Interaction Tests**
   - Test help command response in Discord environment
   - Verify ephemeral message behavior
   - Test with different user roles in actual Discord server

2. **End-to-End Tests**
   - Test complete help command flow for each user type
   - Verify proper role-based filtering in live environment
   - Test error handling with actual Discord API responses

### Performance Tests
1. **Response Time Tests**
   - Measure help command response time
   - Test with large numbers of commands
   - Verify embed size stays within Discord limits

2. **Memory Usage Tests**
   - Monitor memory usage during help command execution
   - Test with multiple concurrent help requests
   - Verify proper cleanup of temporary objects