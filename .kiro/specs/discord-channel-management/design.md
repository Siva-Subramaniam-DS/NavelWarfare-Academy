# Design Document

## Overview

This design outlines the changes needed to update Discord channel IDs for the tournament system and remove transcript channel functionality. The current system uses a centralized `CHANNEL_IDS` dictionary that needs to be updated with new channel IDs and cleaned of transcript references.

## Architecture

The channel management system follows a centralized configuration pattern where all channel IDs are stored in a single dictionary at the module level. This design maintains the existing architecture while updating the channel mappings and removing unused functionality.

### Current Architecture
- `CHANNEL_IDS` dictionary stores all channel mappings
- Functions reference channels via `CHANNEL_IDS["channel_name"]`
- Bot retrieves channels using `interaction.guild.get_channel(CHANNEL_IDS["channel_name"])`

### Updated Architecture
- Same centralized dictionary approach
- Updated channel ID values
- Removed transcript channel entry
- All existing functionality patterns remain unchanged

## Components and Interfaces

### Channel Configuration Component

**Location**: `app.py` (lines 27-33)

**Current State**:
```python
CHANNEL_IDS = {
    "take_schedule": 1242280627991220275,
    "results": 1281967638360359067,
    "staff_attendance": 1378979992641339403,
    "transcript": 1175720148259324017
}
```

**Updated State**:
```python
CHANNEL_IDS = {
    "take_schedule": 1281967703506026538,  # Updated schedule channel
    "results": 1281967638360359067,        # Remains the same
    "staff_attendance": 1378979992641339403 # Remains the same
    # transcript entry removed entirely
}
```

### Channel Usage Points

**Schedule Channel Usage**:
- Location: Line 1440 in `create_schedule` command
- Function: Posts schedule messages with take schedule buttons
- Impact: Will now post to new schedule channel ID

**Results Channel Usage**:
- Location: Line 1591 in result posting functionality
- Function: Posts match results with screenshots
- Impact: No change needed (ID remains the same)

**Staff Attendance Channel Usage**:
- Location: Line 1607 in attendance tracking
- Function: Posts staff attendance messages
- Impact: No change needed (ID remains the same)

**Transcript Channel Usage**:
- Location: Line 31 in CHANNEL_IDS definition
- Function: Currently defined but not actively used in the codebase
- Impact: Will be completely removed

## Data Models

### Channel ID Mapping
```python
CHANNEL_IDS: Dict[str, int] = {
    "take_schedule": int,    # Schedule channel for posting match schedules
    "results": int,          # Results channel for posting match outcomes  
    "staff_attendance": int  # Attendance channel for staff tracking
}
```

### Channel Access Pattern
```python
# Standard pattern used throughout the codebase
channel = interaction.guild.get_channel(CHANNEL_IDS["channel_name"])
if channel:
    await channel.send(content, embed=embed)
```

## Error Handling

### Channel Access Validation
The existing error handling pattern will remain unchanged:
- Check if channel exists before attempting to send messages
- Graceful degradation if channel is not found
- Error logging for debugging purposes

### Migration Safety
- Channel ID updates are atomic (single dictionary update)
- No breaking changes to existing functionality
- Backward compatibility maintained for all active features

## Testing Strategy

### Unit Testing Approach
1. **Configuration Validation**:
   - Verify CHANNEL_IDS contains correct channel IDs
   - Confirm transcript channel is not present
   - Validate all required channels are defined

2. **Channel Access Testing**:
   - Mock Discord guild.get_channel() calls
   - Test each channel usage point with new IDs
   - Verify error handling for non-existent channels

3. **Integration Testing**:
   - Test schedule posting to new schedule channel
   - Verify results posting still works correctly
   - Confirm attendance tracking functions properly

### Manual Testing Checklist
1. **Schedule Functionality**:
   - Create a new schedule and verify it posts to channel 1281967703506026538
   - Confirm take schedule buttons work correctly
   - Verify judge assignment notifications appear in correct channel

2. **Results Functionality**:
   - Post match results and confirm they appear in channel 1281967638360359067
   - Test screenshot attachments work correctly

3. **Attendance Functionality**:
   - Trigger attendance tracking and verify messages appear in channel 1378979992641339403

4. **Transcript Removal Verification**:
   - Search codebase for any remaining transcript references
   - Confirm no functionality attempts to access transcript channels
   - Verify bot startup doesn't reference transcript channel

### Rollback Strategy
If issues arise after deployment:
1. Revert CHANNEL_IDS dictionary to previous values
2. Re-add transcript entry if any hidden dependencies are discovered
3. Test all functionality with original channel IDs
4. Investigate and fix any discovered issues before re-attempting update

## Implementation Notes

### Code Changes Required
1. **Primary Change**: Update CHANNEL_IDS dictionary values
2. **Cleanup**: Remove transcript channel entry
3. **Verification**: Ensure no other transcript references exist

### Deployment Considerations
- Changes take effect immediately upon bot restart
- No database migrations required
- No user-facing interface changes
- Existing scheduled events will continue to work with new channel IDs

### Documentation Updates
- Update README.md if it contains channel ID references
- Update any configuration documentation
- Ensure deployment guides reflect new channel IDs