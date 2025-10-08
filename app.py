import discord
from discord import app_commands
from discord.ext import commands
import os
import random
from dotenv import load_dotenv
from itertools import combinations
from typing import Optional
import re
import datetime
import asyncio
import glob
from discord.ui import Button, View
import pytz
from PIL import Image, ImageDraw, ImageFont
# Removed pilmoji import due to dependency issues
import io
import json
from pathlib import Path
import requests
import tempfile

# Load environment variables
load_dotenv()

# Channel IDs for event management
CHANNEL_IDS = {
    "take_schedule": 1281967638360359067,    # Schedule channel for posting match schedules
    "results": 1281967703506026538,          # Results channel for posting match outcomes
    "staff_attendance": 1378979992641339403  # Attendance channel for staff tracking
}

# Bot owner ID - has access to all commands
BOT_OWNER_ID = 1251442077561131059

# Role IDs for permissions
ROLE_IDS = {
    "judge": 1261723119257915412,        # Judge role
    "bot_op": 1242280627991220275,       # Bot operator role (like helper head and helper team)
    "organizer": 1314905337437880340,    # Organizer role
    "bot_admin": 1242280443898761236     # Bot admin role (full server permissions)
}

# Branding constants
ORGANIZATION_NAME = "Naval Warfare Academy"
TOURNAMENT_SYSTEM_NAME = "Naval Warfare Academy Tournament System"

# Set Windows event loop policy for asyncio
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Store scheduled events for reminders
scheduled_events = {}

# Load scheduled events from file on startup
def load_scheduled_events():
    global scheduled_events
    try:
        if os.path.exists('scheduled_events.json'):
            with open('scheduled_events.json', 'r') as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects
                for event_id, event_data in data.items():
                    if 'datetime' in event_data:
                        event_data['datetime'] = datetime.datetime.fromisoformat(event_data['datetime'])
                scheduled_events = data
                print(f"Loaded {len(scheduled_events)} scheduled events from file")
    except Exception as e:
        print(f"Error loading scheduled events: {e}")
        scheduled_events = {}

# Save scheduled events to file
def save_scheduled_events():
    try:
        # Convert datetime objects to strings for JSON serialization
        data_to_save = {}
        for event_id, event_data in scheduled_events.items():
            event_copy = event_data.copy()
            if 'datetime' in event_copy:
                event_copy['datetime'] = event_copy['datetime'].isoformat()
            # Remove non-serializable objects like discord.Member
            if 'judge' in event_copy:
                event_copy['judge'] = None
            data_to_save[event_id] = event_copy
        
        with open('scheduled_events.json', 'w') as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving scheduled events: {e}")

# Track per-event reminder tasks (for cancellation/update)
reminder_tasks = {}

# Track per-event cleanup tasks (to remove finished events after result)
cleanup_tasks = {}

# Store judge assignments to prevent overloading
judge_assignments = {}  # {judge_id: [event_ids]}

# ===========================================================================================
# RULE MANAGEMENT SYSTEM
# ===========================================================================================

# Store tournament rules in memory
tournament_rules = {}

def load_rules():
    """Load rules from persistent storage"""
    global tournament_rules
    try:
        if os.path.exists('tournament_rules.json'):
            with open('tournament_rules.json', 'r', encoding='utf-8') as f:
                tournament_rules = json.load(f)
                print(f"Loaded tournament rules from file")
        else:
            tournament_rules = {}
            print("No existing rules file found, starting with empty rules")
    except Exception as e:
        print(f"Error loading tournament rules: {e}")
        tournament_rules = {}

def save_rules():
    """Save rules to persistent storage"""
    try:
        with open('tournament_rules.json', 'w', encoding='utf-8') as f:
            json.dump(tournament_rules, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving tournament rules: {e}")
        return False

def get_current_rules():
    """Get current rules content"""
    return tournament_rules.get('rules', {}).get('content', '')

def set_rules_content(content, user_id, username):
    """Set new rules content with metadata"""
    global tournament_rules
    
    # Sanitize content (basic cleanup)
    if content:
        content = content.strip()
    
    # Update rules with metadata
    tournament_rules['rules'] = {
        'content': content,
        'last_updated': datetime.datetime.utcnow().isoformat(),
        'updated_by': {
            'user_id': user_id,
            'username': username
        },
        'version': tournament_rules.get('rules', {}).get('version', 0) + 1
    }
    
    return save_rules()

def has_organizer_permission(interaction):
    """Check if user has organizer permissions for rule management (Bot Owner or Organizer)"""
    # Bot Owner bypass
    if interaction.user.id == BOT_OWNER_ID:
        return True
    
    organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"])
    return organizer_role is not None

# Embed field utility functions for safe Discord.py embed manipulation
def find_field_index(embed: discord.Embed, field_name: str) -> int:
    """Find the index of a field by name. Returns -1 if not found."""
    try:
        for i, field in enumerate(embed.fields):
            if field.name == field_name:
                return i
        return -1
    except Exception as e:
        print(f"Error finding field index: {e}")
        return -1

def remove_field_by_name(embed: discord.Embed, field_name: str) -> bool:
    """Safely remove a field by name using Discord.py methods. Returns True if removed, False if not found."""
    try:
        field_index = find_field_index(embed, field_name)
        if field_index != -1:
            embed.remove_field(field_index)
            return True
        return False
    except Exception as e:
        print(f"Error removing field by name '{field_name}': {e}")
        return False

def update_judge_field(embed: discord.Embed, judge_member: discord.Member) -> bool:
    """Update or add judge field safely. Returns True if successful."""
    try:
        # Remove existing judge field if it exists
        remove_field_by_name(embed, "👨‍⚖️ Judge")
        
        # Add new judge field
        embed.add_field(
            name="👨‍⚖️ Judge", 
            value=f"{judge_member.mention} `@{judge_member.name}`", 
            inline=True
        )
        return True
    except Exception as e:
        print(f"Error updating judge field: {e}")
        return False

def remove_judge_field(embed: discord.Embed) -> bool:
    """Remove judge field safely. Returns True if removed, False if not found."""
    try:
        return remove_field_by_name(embed, "👨‍⚖️ Judge")
    except Exception as e:
        print(f"Error removing judge field: {e}")
        return False

def add_green_circle_to_title(title: str) -> str:
    """Add green circle emoji to the beginning of title if not already present"""
    green_circle = "🟢"
    
    # Check if already has green circle
    if title and title.startswith(green_circle):
        return title
    
    # Add green circle to beginning
    return green_circle + (title or "")

def update_embed_title_with_green_circle(embed: discord.Embed) -> bool:
    """Update embed title with green circle, returns success status"""
    try:
        if embed.title:
            new_title = add_green_circle_to_title(embed.title)
            embed.title = new_title
            return True
        return False
    except Exception as e:
        print(f"Error updating embed title with green circle: {e}")
        return False

def replace_green_circle_with_checkmark(title: str) -> str:
    """Replace green circle emoji with checkmark emoji in title"""
    green_circle = "🟢"
    checkmark = "✅"
    
    if title and title.startswith(green_circle):
        return checkmark + title[len(green_circle):]
    
    # If no green circle, just add checkmark at the beginning
    return checkmark + (title or "")

def update_embed_title_with_checkmark(embed: discord.Embed) -> bool:
    """Update embed title with checkmark, returns success status"""
    try:
        if embed.title:
            new_title = replace_green_circle_with_checkmark(embed.title)
            embed.title = new_title
            return True
        return False
    except Exception as e:
        print(f"Error updating embed title with checkmark: {e}")
        return False

def check_bot_permissions(channel: discord.TextChannel) -> dict:
    """Check if bot has necessary permissions in a channel"""
    if not channel:
        return {"can_edit": False, "reason": "Channel not found"}
    
    bot_member = channel.guild.me
    if not bot_member:
        return {"can_edit": False, "reason": "Bot not found in guild"}
    
    permissions = channel.permissions_for(bot_member)
    
    required_perms = {
        "read_messages": permissions.read_messages,
        "send_messages": permissions.send_messages,
        "embed_links": permissions.embed_links,
        "read_message_history": permissions.read_message_history
    }
    
    missing_perms = [perm for perm, has_perm in required_perms.items() if not has_perm]
    
    if missing_perms:
        return {"can_edit": False, "reason": f"Missing permissions: {', '.join(missing_perms)}"}
    
    return {"can_edit": True, "reason": "All permissions available"}

def can_judge_take_schedule(judge_id: int, max_assignments: int = 3) -> tuple[bool, str]:
    """Check if a judge can take another schedule"""
    if judge_id not in judge_assignments:
        return True, ""
    
    current_assignments = len(judge_assignments[judge_id])
    if current_assignments >= max_assignments:
        return False, f"You already have {current_assignments} schedule(s) assigned. Maximum allowed is {max_assignments}."
    
    return True, ""

def add_judge_assignment(judge_id: int, event_id: str):
    """Add a schedule assignment to a judge"""
    if judge_id not in judge_assignments:
        judge_assignments[judge_id] = []
    judge_assignments[judge_id].append(event_id)

def remove_judge_assignment(judge_id: int, event_id: str):
    """Remove a schedule assignment from a judge"""
    if judge_id in judge_assignments and event_id in judge_assignments[judge_id]:
        judge_assignments[judge_id].remove(event_id)
        if not judge_assignments[judge_id]:  # Remove empty list
            del judge_assignments[judge_id]

class TakeScheduleButton(View):
    def __init__(self, event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, event_channel: discord.TextChannel = None):
        super().__init__(timeout=None)
        self.event_id = event_id
        self.team1_captain = team1_captain
        self.team2_captain = team2_captain
        self.event_channel = event_channel
        self.judge = None
        self._taking_schedule = False  # Flag to prevent race conditions
        
    @discord.ui.button(label="Take Schedule", style=discord.ButtonStyle.green, emoji="📋")
    async def take_schedule(self, interaction: discord.Interaction, button: Button):
        # Prevent race conditions by checking if someone is already taking the schedule
        if self._taking_schedule:
            await interaction.response.send_message("⏳ Another judge is currently taking this schedule. Please wait a moment.", ephemeral=True)
            return
            
        # Check if user has Judge or Organizer role, or is Bot Owner
        if interaction.user.id != BOT_OWNER_ID:
            organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"])
            judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"])
            if not (organizer_role or judge_role):
                await interaction.response.send_message("❌ You need **Organizer** or **Judge** role to take this schedule.", ephemeral=True)
                return
            
        # Check if already taken
        if self.judge:
            await interaction.response.send_message(f"❌ This schedule has already been taken by {self.judge.display_name}.", ephemeral=True)
            return
        
        # Check if judge can take more schedules
        can_take, error_message = can_judge_take_schedule(interaction.user.id, max_assignments=7)
        if not can_take:
            await interaction.response.send_message(f"❌ {error_message}", ephemeral=True)
            return
        
        # Set flag to prevent race conditions
        self._taking_schedule = True
        
        try:
            # Defer response to give us time to process
            await interaction.response.defer(ephemeral=True)
            
            # Double-check if still available (in case another judge took it while we were processing)
            if self.judge:
                await interaction.followup.send(f"❌ This schedule has already been taken by {self.judge.display_name}.", ephemeral=True)
                return
            
            # Assign judge
            self.judge = interaction.user
            
            # Add to judge assignments tracking
            add_judge_assignment(interaction.user.id, self.event_id)
            
            # Update button appearance
            button.label = f"Taken by {interaction.user.display_name}"
            button.style = discord.ButtonStyle.gray
            button.disabled = True
            button.emoji = "✅"
            
            # Update the embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            
            # Update title with green circle
            title_update_success = update_embed_title_with_green_circle(embed)
            if not title_update_success:
                print(f"Warning: Failed to update title for event {self.event_id}")
            
            # Update judge field using safe utility function
            if not update_judge_field(embed, interaction.user):
                await interaction.followup.send("❌ Failed to update embed with judge information.", ephemeral=True)
                return
            
            # Update the message with the updated take button only
            try:
                await interaction.message.edit(embed=embed, view=self)
            except discord.Forbidden:
                await interaction.followup.send("❌ Bot doesn't have permission to edit messages in this channel.", ephemeral=True)
                return
            except Exception as e:
                print(f"Error editing message: {e}")
                await interaction.followup.send("❌ Failed to update message.", ephemeral=True)
                return
            
            # Send success message
            await interaction.followup.send("✅ You have successfully taken this schedule!", ephemeral=True)
            
            # Send notification to the event channel
            await self.send_judge_assignment_notification(interaction.user)
            
            # Update scheduled events with judge
            if self.event_id in scheduled_events:
                scheduled_events[self.event_id]['judge'] = self.judge
            
        except Exception as e:
            # Reset flag in case of error
            self._taking_schedule = False
            print(f"Error in take_schedule: {e}")
            await interaction.followup.send(f"❌ An error occurred while taking the schedule: {str(e)}", ephemeral=True)
        finally:
            # Reset flag after processing
            self._taking_schedule = False

    
    async def send_judge_assignment_notification(self, judge: discord.Member):
        """Send notification to the event channel when a judge is assigned and add judge to channel"""
        if not self.event_channel:
            return
        
        try:
            # Add judge to the event channel with proper permissions
            await self.event_channel.set_permissions(
                judge, 
                read_messages=True, 
                send_messages=True, 
                view_channel=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True
            )
            
            # Create notification embed
            embed = discord.Embed(
                title="👨‍⚖️ Judge Assigned",
                description=f"**{judge.display_name}** has been assigned as the judge for this match!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📋 Match Details",
                value=f"**Team 1:** {self.team1_captain.mention}\n**Team 2:** {self.team2_captain.mention}",
                inline=False
            )
            
            embed.add_field(
                name="👨‍⚖️ Judge",
                value=f"{judge.mention} `@{judge.name}`\n✅ **Added to channel**",
                inline=True
            )
            
            embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
            
            # Send notification to the event channel
            await self.event_channel.send(
                content=f"🔔 {judge.mention} {self.team1_captain.mention} {self.team2_captain.mention}",
                embed=embed
            )
            
        except discord.Forbidden:
            print(f"Error: Bot doesn't have permission to add {judge.display_name} to channel {self.event_channel.name}")
        except Exception as e:
            print(f"Error sending judge assignment notification: {e}")
    
    





# ===========================================================================================
# RULE MANAGEMENT UI COMPONENTS
# ===========================================================================================

class RuleInputModal(discord.ui.Modal):
    """Modal for entering/editing rule content"""
    
    def __init__(self, title: str, current_content: str = ""):
        super().__init__(title=title)
        
        # Text input field for rule content
        self.rule_input = discord.ui.TextInput(
            label="Tournament Rules",
            placeholder="Enter the tournament rules here...",
            default=current_content,
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=False
        )
        self.add_item(self.rule_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the content from the input
            content = self.rule_input.value.strip()
            
            # Save the rules
            success = set_rules_content(content, interaction.user.id, interaction.user.name)
            
            if success:
                # Create confirmation embed
                embed = discord.Embed(
                    title="✅ Rules Updated Successfully",
                    description="Tournament rules have been saved.",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                
                if content:
                    # Show preview of rules (truncated if too long)
                    preview = content[:500] + "..." if len(content) > 500 else content
                    embed.add_field(name="Rules Preview", value=f"```\n{preview}\n```", inline=False)
                else:
                    embed.add_field(name="Status", value="Rules have been cleared (empty)", inline=False)
                
                embed.set_footer(text=f"Updated by {interaction.user.name}")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Failed to save rules. Please try again.", ephemeral=True)
                
        except Exception as e:
            print(f"Error in rule modal submission: {e}")
            await interaction.response.send_message("❌ An error occurred while saving rules.", ephemeral=True)

class RulesManagementView(discord.ui.View):
    """Interactive view for organizers with rule management buttons"""
    
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
    
    @discord.ui.button(label="Enter Rules", style=discord.ButtonStyle.green, emoji="📝")
    async def enter_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to enter new rules"""
        modal = RuleInputModal("Enter Tournament Rules")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Reedit Rules", style=discord.ButtonStyle.primary, emoji="✏️")
    async def reedit_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to edit existing rules"""
        current_rules = get_current_rules()
        
        if not current_rules:
            await interaction.response.send_message("❌ No rules are currently set. Use 'Enter Rules' to create new rules.", ephemeral=True)
            return
        
        modal = RuleInputModal("Edit Tournament Rules", current_rules)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Show Rules", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def show_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to display current rules"""
        await display_rules(interaction)

async def display_rules(interaction: discord.Interaction):
    """Display current tournament rules in an embed"""
    try:
        global tournament_rules
        current_rules = get_current_rules()
        
        if not current_rules:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description="No tournament rules have been set yet.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text=TOURNAMENT_SYSTEM_NAME)
        else:
            embed = discord.Embed(
                title="📋 Tournament Rules",
                description=current_rules,
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add metadata if available
            if 'rules' in tournament_rules and 'last_updated' in tournament_rules['rules']:
                updated_by = tournament_rules['rules'].get('updated_by', {}).get('username', 'Unknown')
                embed.set_footer(text=f"{ORGANIZATION_NAME} • Last updated by {updated_by}")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
    except Exception as e:
        print(f"Error displaying rules: {e}")
        await interaction.response.send_message("❌ An error occurred while displaying rules.", ephemeral=False)

# ===========================================================================================
# NOTIFICATION AND REMINDER SYSTEM (Ten-minute reminder for captains and judge)
# ===========================================================================================

async def send_ten_minute_reminder(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel, match_time: datetime.datetime):
    """Send 10-minute reminder notification to judge and captains"""
    try:
        if not event_channel:
            print(f"No event channel provided for event {event_id}")
            return

        # Get the latest judge from scheduled_events if available
        resolved_judge = judge
        if event_id in scheduled_events:
            stored_judge = scheduled_events[event_id].get('judge')
            if stored_judge:
                resolved_judge = stored_judge

        # Create reminder embed
        embed = discord.Embed(
            title="⏰ 10-MINUTE MATCH REMINDER",
            description=f"**Your tournament match is starting in 10 minutes!**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🕒 Match Time", value=f"<t:{int(match_time.timestamp())}:F>", inline=False)
        embed.add_field(name="👥 Team Captains", value=f"{team1_captain.mention} vs {team2_captain.mention}", inline=False)
        if resolved_judge:
            embed.add_field(name="👨‍⚖️ Judge", value=f"{resolved_judge.mention}", inline=False)
        embed.add_field(name="� ActAion Required", value="Please prepare for the match and join the designated channel.", inline=False)
        embed.set_footer(text="Tournament Management System")

        # Send notification with pings
        pings = f"{team1_captain.mention} {team2_captain.mention}"
        if resolved_judge:
            pings = f"{resolved_judge.mention} " + pings
        notification_text = f"🔔 **MATCH REMINDER**\n\n{pings}\n\nYour match starts in **10 minutes**!"

        await event_channel.send(content=notification_text, embed=embed)
        print(f"10-minute reminder sent for event {event_id}")
    except Exception as e:
        print(f"Error sending 10-minute reminder for event {event_id}: {e}")


async def schedule_ten_minute_reminder(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel, match_time: datetime.datetime):
    """Schedule a 10-minute reminder for the match"""
    try:
        # Calculate when to send the 10-minute reminder
        reminder_time = match_time - datetime.timedelta(minutes=10)
        now = datetime.datetime.now(pytz.UTC)

        # Ensure match_time and reminder_time are timezone-aware UTC
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=pytz.UTC)
            reminder_time = match_time - datetime.timedelta(minutes=10)

        # Check if reminder time is in the future
        if reminder_time <= now:
            print(f"Reminder time for event {event_id} is in the past, skipping")
            return

        # Calculate delay in seconds
        delay_seconds = (reminder_time - now).total_seconds()

        async def reminder_task():
            try:
                await asyncio.sleep(delay_seconds)
                await send_ten_minute_reminder(event_id, team1_captain, team2_captain, judge, event_channel, match_time)
            except asyncio.CancelledError:
                print(f"Reminder task for event {event_id} was cancelled")
            except Exception as e:
                print(f"Error in reminder task for event {event_id}: {e}")

        # Cancel existing reminder if any
        if event_id in reminder_tasks:
            reminder_tasks[event_id].cancel()

        # Schedule new reminder
        reminder_tasks[event_id] = asyncio.create_task(reminder_task())
        print(f"10-minute reminder scheduled for event {event_id} at {reminder_time}")
    except Exception as e:
        print(f"Error scheduling 10-minute reminder for event {event_id}: {e}")


async def schedule_event_reminder_v2(event_id: str, team1_captain: discord.Member, team2_captain: discord.Member, judge: Optional[discord.Member], event_channel: discord.TextChannel):
    """Schedule event reminder with 10-minute notification using stored event datetime"""
    try:
        if event_id not in scheduled_events:
            print(f"Event {event_id} not found in scheduled_events")
            return
        event_data = scheduled_events[event_id]
        match_time = event_data.get('datetime')
        if not match_time:
            print(f"No datetime found for event {event_id}")
            return
        # Ensure timezone-aware UTC
        if match_time.tzinfo is None:
            match_time = match_time.replace(tzinfo=pytz.UTC)
        await schedule_ten_minute_reminder(event_id, team1_captain, team2_captain, judge, event_channel, match_time)
    except Exception as e:
        print(f"Error in schedule_event_reminder_v2 for event {event_id}: {e}")

async def schedule_event_cleanup(event_id: str, delay_hours: int = 24):
    """Schedule cleanup to remove an event after delay_hours (default 24h)."""
    try:
        if event_id not in scheduled_events:
            return
        delay_seconds = delay_hours * 3600

        async def cleanup_task():
            try:
                await asyncio.sleep(delay_seconds)
                data = scheduled_events.get(event_id)
                if not data:
                    return
                # Delete original schedule message if known
                try:
                    guilds = bot.guilds
                    for guild in guilds:
                        ch_id = data.get('schedule_channel_id')
                        msg_id = data.get('schedule_message_id')
                        if ch_id and msg_id:
                            channel = guild.get_channel(ch_id)
                            if channel:
                                try:
                                    msg = await channel.fetch_message(msg_id)
                                    await msg.delete()
                                except discord.NotFound:
                                    pass
                                except Exception as e:
                                    print(f"Error deleting schedule message for {event_id}: {e}")
                except Exception as e:
                    print(f"Guild/channel fetch error during cleanup for {event_id}: {e}")

                # Clean up poster file if any
                try:
                    poster_path = data.get('poster_path')
                    if poster_path and os.path.exists(poster_path):
                        os.remove(poster_path)
                except Exception as e:
                    print(f"Poster cleanup error for {event_id}: {e}")

                # Remove any reminder task
                try:
                    if event_id in reminder_tasks:
                        reminder_tasks[event_id].cancel()
                        del reminder_tasks[event_id]
                except Exception:
                    pass

                # Finally remove from scheduled events and persist
                try:
                    if event_id in scheduled_events:
                        del scheduled_events[event_id]
                        save_scheduled_events()
                except Exception as e:
                    print(f"Error removing event {event_id} in cleanup: {e}")
            except asyncio.CancelledError:
                print(f"Cleanup task for event {event_id} was cancelled")
            except Exception as e:
                print(f"Error in cleanup task for event {event_id}: {e}")

        # Cancel existing cleanup if any and schedule new
        if event_id in cleanup_tasks:
            try:
                cleanup_tasks[event_id].cancel()
            except Exception:
                pass

        cleanup_tasks[event_id] = asyncio.create_task(cleanup_task())
        print(f"Cleanup scheduled for event {event_id} in {delay_hours} hours")
    except Exception as e:
        print(f"Error scheduling cleanup for event {event_id}: {e}")

# Google Fonts API Integration
def download_google_font(font_family: str, font_style: str = "regular", font_weight: str = "400") -> str:
    """Download a font from Google Fonts API and return the local file path"""
    try:
        # Google Fonts API URL
        api_url = f"https://fonts.googleapis.com/css2?family={font_family.replace(' ', '+')}:wght@{font_weight}"
        
        # Add style parameter if not regular
        if font_style != "regular":
            api_url += f"&style={font_style}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse CSS to get font URL
        css_content = response.text
        font_urls = re.findall(r'url\((https://[^)]+\.woff2?)\)', css_content)
        
        if not font_urls:
            print(f"No font URLs found in CSS for {font_family}")
            return None
        
        # Download the first font file (usually woff2)
        font_url = font_urls[0]
        font_response = requests.get(font_url, timeout=15)
        font_response.raise_for_status()
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.woff2')
        temp_file.write(font_response.content)
        temp_file.close()
        
        print(f"Downloaded Google Font: {font_family} -> {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        print(f"Error downloading Google Font {font_family}: {e}")
        return None

def get_font_with_fallbacks(font_name: str, size: int, font_style: str = "regular") -> ImageFont.FreeTypeFont:
    """Get a font with multiple fallback options including Google Fonts"""
    font_candidates = []
    
    # 1. Try Google Fonts first
    try:
        google_font_path = download_google_font(font_name, font_style)
        if google_font_path:
            font_candidates.append(google_font_path)
    except Exception as e:
        print(f"Google Fonts failed for {font_name}: {e}")
    
    # 2. Try local bundled fonts
    local_fonts = [
        str(Path("Fonts") / "capture_it" / "Capture it.ttf"),
        str(Path("Fonts") / "ds_digital" / "DS-DIGIB.TTF"),
        str(Path("Fonts") / "ds_digital" / "DS-DIGII.TTF"),
        str(Path("Fonts") / "ds_digital" / "DS-DIGI.TTF"),
    ]
    font_candidates.extend(local_fonts)
    
    # 3. Try system fonts
    system_fonts = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf", 
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
    ]
    font_candidates.extend(system_fonts)
    
    # Try each font candidate
    for font_path in font_candidates:
        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, size)
                print(f"Successfully loaded font: {font_path}")
                return font
        except Exception as e:
            print(f"Failed to load font {font_path}: {e}")
            continue
    
    # Final fallback to default font
    print(f"All fonts failed, using default font for size {size}")
    try:
        return ImageFont.load_default().font_variant(size=size)
    except:
        return ImageFont.load_default()

def sanitize_username_for_poster(username: str) -> str:
    """Convert Discord display names to poster-friendly ASCII by stripping emojis and fancy Unicode.

    - Normalizes to NFKD and drops non-ASCII codepoints
    - Collapses repeated whitespace and trims ends
    - Falls back to 'Player' if empty after sanitization
    """
    try:
        import unicodedata
        # Normalize and strip accents/fancy letters
        normalized = unicodedata.normalize('NFKD', str(username))
        ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
        # Remove remaining characters that might be control or non-printable
        ascii_only = re.sub(r"[^\x20-\x7E]", "", ascii_only)
        # Collapse whitespace
        ascii_only = re.sub(r"\s+", " ", ascii_only).strip()
        return ascii_only if ascii_only else "Player"
    except Exception:
        return str(username) if username else "Player"

def get_random_template():
    """Get a random template image from the Templates folder"""
    template_path = "Templates"
    if os.path.exists(template_path):
        # Get all image files
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif']
        image_files = []
        for ext in image_extensions:
            image_files.extend(glob.glob(os.path.join(template_path, ext)))
            image_files.extend(glob.glob(os.path.join(template_path, ext.upper())))
        
        if image_files:
            return random.choice(image_files)
    return None

def create_event_poster(template_path: str, round_label: str, team1_captain: str, team2_captain: str, utc_time: str, date_str: str = None, tournament_name: str = "King of the Seas", server_name: str = ORGANIZATION_NAME) -> str:
    """Create event poster with text overlays using Google Fonts and improved error handling"""
    print(f"Creating poster with template: {template_path}")
    
    try:
        # Validate template path
        if not os.path.exists(template_path):
            print(f"Template file not found: {template_path}")
            return None
            
        # Open the template image
        with Image.open(template_path) as img:
            print(f"Opened template image: {img.size}, mode: {img.mode}")
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Resize image to be smaller (max 800x600 to avoid Discord size limits)
            max_width, max_height = 800, 600
            width, height = img.size
            
            # Calculate new dimensions while maintaining aspect ratio
            if width > max_width or height > max_height:
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"Resized image to: {new_width}x{new_height}")
            
            # Create a copy to work with
            poster = img.copy()
            draw = ImageDraw.Draw(poster)
            
            # Get final image dimensions
            width, height = poster.size
            
            # Load fonts using the new system with Google Fonts integration
            print("Loading fonts...")
            
            # Define font sizes based on image height (reduced for better fit)
            title_size = int(height * 0.10)
            round_size = int(height * 0.14)
            vs_size = int(height * 0.09)
            time_size = int(height * 0.07)
            tiny_size = int(height * 0.05)
            
            # Load fonts with Google Fonts fallback
            try:
                # Try Google Fonts first, then fallback to local/system fonts
                font_title = get_font_with_fallbacks("Orbitron", title_size, "bold")  # Modern display font
                font_round = get_font_with_fallbacks("Orbitron", round_size, "bold")  # Same for round
                # Use a unique bundled font for player names so styling is consistent regardless of Discord nickname styling
                font_vs = get_font_with_fallbacks("Capture it", vs_size, "bold")       # Unique display font from Fonts/capture_it
                font_time = get_font_with_fallbacks("Share Tech Mono", time_size)     # Monospace for time
                font_tiny = get_font_with_fallbacks("Roboto", tiny_size)              # Small text
                
                print("Fonts loaded successfully")
                
            except Exception as font_error:
                print(f"Font loading error: {font_error}")
                # Ultimate fallback to default fonts
                font_title = ImageFont.load_default()
                font_round = ImageFont.load_default()
                font_vs = ImageFont.load_default()
                font_time = ImageFont.load_default()
                font_tiny = ImageFont.load_default()
            
            # Define colors for clean visibility
            text_color = (255, 255, 255)  # Bright white
            outline_color = (0, 0, 0)     # Pure black
            yellow_color = (255, 255, 0)  # Bright yellow for important text
            
            # Helper function to draw text with outline
            def draw_text_with_outline(text, x, y, font, text_color=text_color, use_yellow=False):
                x, y = int(x), int(y)
                final_text_color = yellow_color if use_yellow else text_color
                
                # Draw thick black outline for visibility
                outline_width = 4
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            try:
                                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
                            except Exception as e:
                                print(f"Error drawing outline: {e}")
                
                # Draw main text on top
                try:
                    draw.text((x, y), text, font=font, fill=final_text_color)
                except Exception as e:
                    print(f"Error drawing main text: {e}")
            
            # Add server name text (top center)
            try:
                server_text = server_name
                server_bbox = draw.textbbox((0, 0), server_text, font=font_title)
                server_width = server_bbox[2] - server_bbox[0]
                server_x = (width - server_width) // 2
                server_y = int(height * 0.08)
                draw_text_with_outline(server_text, server_x, server_y, font_title)
                print(f"Added server name: {server_text}")
            except Exception as e:
                print(f"Error adding server name: {e}")
            
            # Add Round text (center) - use yellow for emphasis
            try:
                round_text = f"ROUND {round_label}"
                round_bbox = draw.textbbox((0, 0), round_text, font=font_round)
                round_width = round_bbox[2] - round_bbox[0]
                round_x = (width - round_width) // 2
                round_y = int(height * 0.35)
                draw_text_with_outline(round_text, round_x, round_y, font_round, use_yellow=True)
                print(f"Added round text: {round_text}")
            except Exception as e:
                print(f"Error adding round text: {e}")
            
            # Add Captain vs Captain text (center)
            try:
                left_name_text = sanitize_username_for_poster(team1_captain)
                vs_core = " VS "
                right_name_text = sanitize_username_for_poster(team2_captain)

                # Measure text components to center the whole line
                left_box = draw.textbbox((0, 0), left_name_text, font=font_vs)
                vs_box = draw.textbbox((0, 0), vs_core, font=font_vs)
                right_box = draw.textbbox((0, 0), right_name_text, font=font_vs)
                
                total_width = (left_box[2] - left_box[0]) + (vs_box[2] - vs_box[0]) + (right_box[2] - right_box[0])
                current_x = (width - total_width) // 2
                vs_y = int(height * 0.55)

                # Draw left name
                draw_text_with_outline(left_name_text, current_x, vs_y, font_vs)
                current_x += (left_box[2] - left_box[0])
                
                # Draw VS
                draw_text_with_outline(vs_core, current_x, vs_y, font_vs, use_yellow=False)
                current_x += (vs_box[2] - vs_box[0])
                
                # Draw right name
                draw_text_with_outline(right_name_text, current_x, vs_y, font_vs)
                
                print(f"Added VS text: {left_name_text} VS {right_name_text}")
            except Exception as e:
                print(f"Error adding VS text: {e}")
            
            # Add date (if provided)
            if date_str:
                try:
                    date_text = f"DATE:  {date_str}"
                    date_bbox = draw.textbbox((0, 0), date_text, font=font_time)
                    date_width = date_bbox[2] - date_bbox[0]
                    date_x = (width - date_width) // 2
                    date_y = int(height * 0.72)
                    draw_text_with_outline(date_text, date_x, date_y, font_time)
                    print(f"Added date: {date_text}")
                except Exception as e:
                    print(f"Error adding date: {e}")
            
            # Add UTC time
            try:
                time_text = f"TIME:  {utc_time}"
                time_bbox = draw.textbbox((0, 0), time_text, font=font_time)
                time_width = time_bbox[2] - time_bbox[0]
                time_x = (width - time_width) // 2
                time_y = int(height * 0.82) if date_str else int(height * 0.75)
                draw_text_with_outline(time_text, time_x, time_y, font_time)
                print(f"Added time: {time_text}")
            except Exception as e:
                print(f"Error adding time: {e}")
            
            # Save the modified image
            output_path = f"temp_poster_{int(datetime.datetime.now().timestamp())}.png"
            poster.save(output_path, "PNG")
            print(f"Poster saved successfully: {output_path}")
            return output_path
            
    except Exception as e:
        print(f"Critical error creating poster: {e}")
        import traceback
        traceback.print_exc()
        return None

def calculate_time_difference(event_datetime: datetime.datetime, user_timezone: str = None) -> dict:
    """Calculate time difference and format for different timezones"""
    current_time = datetime.datetime.now()
    time_diff = event_datetime - current_time
    minutes_remaining = int(time_diff.total_seconds() / 60)
    
    # Format UTC time exactly as requested
    utc_time_str = event_datetime.strftime("%H:%M utc, %d/%m")
    
    # Try to detect user's local timezone
    local_timezone = None
    if user_timezone:
        try:
            local_timezone = pytz.timezone(user_timezone)
        except:
            pass
    
    # If no user timezone provided, try to detect from system
    if not local_timezone:
        try:
            # Try to get system timezone
            import time
            local_timezone = pytz.timezone(time.tzname[time.daylight])
        except:
            # Fallback to IST if detection fails
            local_timezone = pytz.timezone('Asia/Kolkata')
    
    # Calculate user's local time
    local_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(local_timezone)
    local_time_formatted = local_time.strftime("%A, %d %B, %Y %H:%M")
    
    # Calculate other common timezones
    ist_tz = pytz.timezone('Asia/Kolkata')
    ist_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(ist_tz)
    ist_formatted = ist_time.strftime("%A, %d %B, %Y %H:%M")
    
    est_tz = pytz.timezone('America/New_York')
    est_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(est_tz)
    est_formatted = est_time.strftime("%A, %d %B, %Y %H:%M")
    
    gmt_tz = pytz.timezone('Europe/London')
    gmt_time = event_datetime.replace(tzinfo=pytz.UTC).astimezone(gmt_tz)
    gmt_formatted = gmt_time.strftime("%A, %d %B, %Y %H:%M")
    
    return {
        'minutes_remaining': minutes_remaining,
        'utc_time': utc_time_str,
        'utc_time_simple': event_datetime.strftime("%H:%M UTC"),
        'local_time': local_time_formatted,
        'ist_time': ist_formatted,
        'est_time': est_formatted,
        'gmt_time': gmt_formatted
    }

def has_event_create_permission(interaction):
    """Check if user has permission to create events (Bot Owner, Organizer or Bot Op)"""
    # Bot Owner bypass
    if interaction.user.id == BOT_OWNER_ID:
        return True
    
    organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"])
    bot_op_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["bot_op"])
    return organizer_role is not None or bot_op_role is not None

def has_event_result_permission(interaction):
    """Check if user has permission to post event results (Bot Owner, Organizer or Judge)"""
    # Bot Owner bypass
    if interaction.user.id == BOT_OWNER_ID:
        return True
    
    organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"])
    judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"])
    return organizer_role is not None or judge_role is not None

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Load scheduled events from file
    load_scheduled_events()
    
    # Load tournament rules from file
    load_rules()
    
    # Reschedule cleanups for any events already marked finished_on if needed (optional)
    try:
        for ev_id, data in list(scheduled_events.items()):
            # If previously scheduled cleanup exists, skip (it won't persist); we don't know result time here
            # Optionally: clean up events older than 7 days to avoid clutter
            try:
                dt = data.get('datetime')
                if isinstance(dt, datetime.datetime):
                    age_days = (datetime.datetime.now() - dt).days
                    if age_days >= 7:
                        # Hard cleanup very old events
                        if ev_id in reminder_tasks:
                            try:
                                reminder_tasks[ev_id].cancel()
                                del reminder_tasks[ev_id]
                            except Exception:
                                pass
                        del scheduled_events[ev_id]
            except Exception:
                pass
        save_scheduled_events()
    except Exception as e:
        print(f"Startup cleanup sweep error: {e}")
    
    # Sync commands with timeout handling
    try:
        print("🔄 Syncing slash commands...")
        import asyncio
        synced = await asyncio.wait_for(tree.sync(), timeout=30.0)
        print(f"✅ Synced {len(synced)} command(s)")
    except asyncio.TimeoutError:
        print("⚠️ Command sync timed out, but bot will continue running")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")
        print("⚠️ Bot will continue running without command sync")
    
    print("🎯 Bot is ready to receive commands!")

@bot.event
async def on_message(message):
    """Handle auto-response commands for ticket management"""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Only process messages that start with ? and are in specific channels
    if not message.content.startswith('?'):
        return
    
    # Check if the command should be restricted to specific channels
    # For now, allow in all channels, but you can add restrictions here
    # Example: if message.channel.id not in [CHANNEL_IDS["take_schedule"], ...]:
    #     return
    
    # Extract command from message
    command = message.content.lower().strip()
    
    # Handle ticket status commands (?sh, ?dq, ?dd, ?ho) - modify channel name prefix
    if command in ['?sh', '?dq', '?dd', '?ho']:
        try:
            # Get the current channel
            channel = message.channel
            
            # Determine the new prefix based on command
            if command == '?sh':
                new_prefix = "🟢"
            elif command == '?dq':
                new_prefix = "🔴"
            elif command == '?dd':
                new_prefix = "✅"
            elif command == '?ho':
                new_prefix = "🟡"
            
            # Get current channel name
            current_name = channel.name
            
            # Remove existing status prefixes if they exist
            clean_name = current_name
            status_prefixes = ["🟢", "🔴", "✅", "🟡"]
            for prefix in status_prefixes:
                if clean_name.startswith(prefix):
                    clean_name = clean_name[len(prefix):].lstrip("-").lstrip()
                    break
            
            # Create new channel name with the status prefix
            new_name = f"{new_prefix}-{clean_name}"
            
            # Update channel name
            await channel.edit(name=new_name)
            
            # Delete the original command message after successful execution
            try:
                await message.delete()
            except discord.Forbidden:
                pass  # Ignore if we can't delete the message
            except Exception:
                pass  # Ignore any other deletion errors
            
        except discord.Forbidden:
            response = await message.channel.send("❌ I don't have permission to edit this channel's name.")
            try:
                await message.delete()
            except:
                pass
        except discord.HTTPException as e:
            response = await message.channel.send(f"❌ Error updating channel name: {e}")
            try:
                await message.delete()
            except:
                pass
        except Exception as e:
            response = await message.channel.send(f"❌ Unexpected error: {e}")
            try:
                await message.delete()
            except:
                pass
        
    elif command == '?b':
        # Challonge URL response
        response = await message.channel.send("https://challonge.com/nwaanniversary")
        # Delete the original command message
        try:
            await message.delete()
        except discord.Forbidden:
            pass  # Ignore if we can't delete the message
        except Exception:
            pass  # Ignore any other deletion errors
    
    # Process other bot commands (important for command processing)
    await bot.process_commands(message)

@tree.command(name="rules", description="Manage or view tournament rules")
async def rules_command(interaction: discord.Interaction):
    """Main rules command with role-based functionality"""
    try:
        # Check if user has organizer permissions
        if has_organizer_permission(interaction):
            # Organizer gets management interface
            embed = discord.Embed(
                title="📋 Tournament Rules Management",
                description="Choose an action to manage tournament rules:",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            current_rules = get_current_rules()
            if current_rules:
                embed.add_field(
                    name="Current Status", 
                    value="✅ Rules are set", 
                    inline=True
                )
                # Show preview of current rules
                preview = current_rules[:200] + "..." if len(current_rules) > 200 else current_rules
                embed.add_field(
                    name="Preview", 
                    value=f"```\n{preview}\n```", 
                    inline=False
                )
            else:
                embed.add_field(
                    name="Current Status", 
                    value="❌ No rules set", 
                    inline=True
                )
            
            embed.set_footer(text=f"{ORGANIZATION_NAME} • Organizer Panel")
            
            # Send with management buttons
            view = RulesManagementView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # Non-organizer gets direct rule display
            await display_rules(interaction)
            
    except Exception as e:
        print(f"Error in rules command: {e}")
        await interaction.response.send_message("❌ An error occurred while processing the rules command.", ephemeral=True)
    
@tree.command(name="team_balance", description="Balance two teams based on player levels")
@app_commands.describe(levels="Comma-separated player levels (e.g. 48,50,51,35,51,50,50,37,51,52)")
async def team_balance(interaction: discord.Interaction, levels: str):
    try:
        level_list = [int(x.strip()) for x in levels.split(",") if x.strip()]
        n = len(level_list)
        if n % 2 != 0:
            await interaction.response.send_message("❌ Number of players must be even (e.g., 8 or 10).", ephemeral=True)
            return

        team_size = n // 2
        min_diff = float('inf')
        best_team_a = []
        for combo in combinations(level_list, team_size):
            team_a = list(combo)
            team_b = list(level_list)
            for lvl in team_a:
                team_b.remove(lvl)
            diff = abs(sum(team_a) - sum(team_b))
            if diff < min_diff:
                min_diff = diff
                best_team_a = team_a
        team_b = list(level_list)
        for lvl in best_team_a:
            team_b.remove(lvl)
        sum_a = sum(best_team_a)
        sum_b = sum(team_b)
        diff = abs(sum_a - sum_b)
        await interaction.response.send_message(
            f"**Team A:** {best_team_a} | Total Level: {sum_a}\n"
            f"**Team B:** {team_b} | Total Level: {sum_b}\n"
            f"**Level Difference:** {diff}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="add_captain", description="Add two captains to a tournament match and rename the channel")
@app_commands.describe(
    round="Round of the tournament (R1-R10, Q, SF, Final)",
    captain1="First captain/team for the match",
    captain2="Second captain/team for the match",
    bracket="Optional bracket identifier (e.g., A, B, Winner, Loser)"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Q"),
        app_commands.Choice(name="Semi Final", value="SF"),
        app_commands.Choice(name="Final", value="Final")
    ]
)
async def add_captain(interaction: discord.Interaction, round: str, captain1: discord.Member, captain2: discord.Member, bracket: str = None):
    """Add two captains to a tournament match and rename the channel with tournament rules."""
    try:
        # Check permissions - only Bot Admin, Organizer, or Bot Op can add captains
        bot_admin_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["bot_admin"])
        organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"])
        bot_op_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["bot_op"])
        
        if not any([bot_admin_role, organizer_role, bot_op_role]):
            await interaction.response.send_message("❌ You don't have permission to use this command. Only Bot Admin, Organizer, or Bot Op can add captains.", ephemeral=True)
            return
        
        # Validate round parameter
        valid_rounds = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "Q", "SF", "Final"]
        if round not in valid_rounds:
            await interaction.response.send_message("❌ Invalid round. Please select R1-R10, Q, SF, or Final.", ephemeral=True)
            return
        
        # Get current channel
        channel = interaction.channel
        
        # Create new channel name
        if bracket:
            new_name = f"{bracket}-{round.lower()}-{captain1.name.lower()}-vs-{captain2.name.lower()}"
        else:
            new_name = f"{round.lower()}-{captain1.name.lower()}-vs-{captain2.name.lower()}"
        
        # Remove special characters and spaces, replace with hyphens
        new_name = re.sub(r'[^a-zA-Z0-9\-]', '-', new_name)
        new_name = re.sub(r'-+', '-', new_name)  # Replace multiple hyphens with single hyphen
        new_name = new_name.strip('-')  # Remove leading/trailing hyphens
        
        # Ensure channel name is within Discord's limits (100 characters max)
        if len(new_name) > 100:
            new_name = new_name[:100]
        
        # Rename the channel
        try:
            await channel.edit(name=new_name)
            await interaction.response.send_message(f"✅ Channel renamed to `{new_name}`", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to rename this channel.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to rename channel: {e}", ephemeral=True)
            return
        
        # Send tournament rules message
        rules_embed = discord.Embed(
            title="🏆 Tournament Match Setup",
            description="Please use this channel for all tournament discussions.",
            color=0x00ff00
        )
        
        # Add logo as thumbnail (top right)
        try:
            with open("animated_1-2.gif", "rb") as logo_file:
                logo_data = io.BytesIO(logo_file.read())
                logo_file = discord.File(logo_data, filename="logo.gif")
                rules_embed.set_thumbnail(url="attachment://logo.gif")
        except FileNotFoundError:
            print("Warning: animated_1-2.gif not found, skipping logo")
        except Exception as e:
            print(f"Warning: Could not load logo: {e}")
        
        rules_embed.add_field(
            name="📋 Tournament Information",
            value=(
                "• Refer to https://discord.com/channels/1242231178208219256/1242280965775036466 for match schedules and pairings.\n"
                "• Refer to https://discord.com/channels/1242231178208219256/1263470544574087169 for official updates.\n"
                "• Refer to https://discord.com/channels/1242231178208219256/1349579975228919868 for tournament guidelines and regulations."
            ),
            inline=False
        )
        
        rules_embed.add_field(
            name="👥 Match Participants",
            value=f"**Round:** {round}\n**Captain 1:** {captain1.mention}\n**Captain 2:** {captain2.mention}",
            inline=False
        )
        
        rules_embed.add_field(
            name="🆘 Need Help?",
            value="If you require any assistance, please ping <@&1424280282571341945> and they will be happy to assist.",
            inline=False
        )
        
        rules_embed.add_field(
            name="🤝 Cooperation",
            value="We appreciate your cooperation and wish you a competitive and fair tournament.",
            inline=False
        )
        
        rules_embed.set_footer(text=f"{ORGANIZATION_NAME} | {interaction.user.name} ✰—• • {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}")
        
        # Send the rules message with logo
        try:
            with open("animated_1-2.gif", "rb") as logo_file:
                logo_data = io.BytesIO(logo_file.read())
                logo_file = discord.File(logo_data, filename="logo.gif")
                await channel.send(embed=rules_embed, file=logo_file)
        except FileNotFoundError:
            print("Warning: animated_1-2.gif not found, sending embed without logo")
            await channel.send(embed=rules_embed)
        except Exception as e:
            print(f"Warning: Could not send logo, sending embed without logo: {e}")
            await channel.send(embed=rules_embed)
        
        
    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in add_captain command: {e}")

@tree.command(name="event", description="Event management commands")
@app_commands.describe(
    action="Select the event action to perform"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="result", value="result")
    ]
)
async def event(interaction: discord.Interaction, action: app_commands.Choice[str]):
    """Base event command - this will be handled by subcommands"""
    await interaction.response.send_message(f"Please use `/event {action.value}` with the appropriate parameters.", ephemeral=True)

@tree.command(name="event-create", description="Creates an event (Bot Admin/Organizer/Bot Op only)")
@app_commands.describe(
    team_1_captain="Captain of team 1",
    team_2_captain="Captain of team 2", 
    hour="Hour of the event (0-23)",
    minute="Minute of the event (0-59)",
    date="Date of the event",
    month="Month of the event",
    round="Round label",
    tournament="Tournament name (e.g. King of the Seas, Summer Cup, etc.)",
    group="Group assignment (A-J) or Winner/Loser"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Qualifier"),
        app_commands.Choice(name="Semi Final", value="Semi Final"),
        app_commands.Choice(name="Final", value="Final"),
    ],
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def event_create(
    interaction: discord.Interaction,
    team_1_captain: discord.Member,
    team_2_captain: discord.Member,
    hour: int,
    minute: int,
    date: int,
    month: int,
    round: app_commands.Choice[str],
    tournament: str,
    group: app_commands.Choice[str] = None
):
    """Creates an event with the specified parameters"""
    
    # Defer the response to give us more time for image processing
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions
    if not has_event_create_permission(interaction):
        await interaction.followup.send("❌ You need **Head Organizer**, **Head Helper** or **Helper Team** role to create events.", ephemeral=True)
        return
    
    # Validate input parameters
    if not (0 <= hour <= 23):
        await interaction.followup.send("❌ Hour must be between 0 and 23", ephemeral=True)
        return
    
    if not (1 <= date <= 31):
        await interaction.followup.send("❌ Date must be between 1 and 31", ephemeral=True)
        return

    if not (1 <= month <= 12):
        await interaction.followup.send("❌ Month must be between 1 and 12", ephemeral=True)
        return
            
    if not (0 <= minute <= 59):
        await interaction.followup.send("❌ Minute must be between 0 and 59", ephemeral=True)
        return

    # Generate unique event ID
    event_id = f"event_{int(datetime.datetime.now().timestamp())}"
    
    # Create event datetime
    current_year = datetime.datetime.now().year
    event_datetime = datetime.datetime(current_year, month, date, hour, minute)
    
    # Calculate time differences and format times
    time_info = calculate_time_difference(event_datetime)
    
    # Resolve round label from choice
    round_label = round.value if isinstance(round, app_commands.Choice) else str(round)
    
    # Resolve group label from choice
    group_label = group.value if group and isinstance(group, app_commands.Choice) else None
    
    # Store event data for reminders
    scheduled_events[event_id] = {
        'title': f"Round {round_label} Match",
        'datetime': event_datetime,
        'time_str': time_info['utc_time'],
        'date_str': f"{date:02d}/{month:02d}",
        'round': round_label,
        'group': group_label,
        'minutes_left': time_info['minutes_remaining'],
        'tournament': tournament,
        'judge': None,
        'channel_id': interaction.channel.id,
        'team1_captain': team_1_captain,
        'team2_captain': team_2_captain
    }
    
    # Save events to file
    save_scheduled_events()
    
    # Get random template image and create poster
    template_image = get_random_template()
    poster_image = None
    
    if template_image:
        try:
            # Create poster with text overlays
            poster_image = create_event_poster(
                template_image, 
                round_label, 
                team_1_captain.name, 
                team_2_captain.name, 
                time_info['utc_time_simple'],
                f"{date:02d}/{month:02d}/{current_year}",
                tournament
            )
            if poster_image:
                # Keep poster path for later cleanup/deletion
                scheduled_events[event_id]['poster_path'] = poster_image
                save_scheduled_events()
        except Exception as e:
            print(f"Error creating poster: {e}")
            poster_image = None
    else:
        print("No template images found in Templates folder")
    
    # Create event embed with new format
    embed = discord.Embed(
        title="Schedule",
        description=f"🗓️ {team_1_captain.display_name} VS {team_2_captain.display_name}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # Tournament and Time Information
    # Create Discord timestamp for automatic timezone conversion
    timestamp = int(event_datetime.timestamp())
    
    # Build event details text
    event_details = f"**Tournament:** {tournament}\n"
    event_details += f"**UTC Time:** {time_info['utc_time']}\n"
    event_details += f"**Local Time:** <t:{timestamp}:F> (<t:{timestamp}:R>)\n"
    event_details += f"**Round:** {round_label}\n"
    
    # Add group if specified
    if group_label:
        event_details += f"**Group:** {group_label}\n"
    
    event_details += f"**Channel:** {interaction.channel.mention}"
    
    embed.add_field(
        name="📋 Event Details", 
        value=event_details,
        inline=False
    )
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Captains Section
    captains_text = f"**Captains**\n"
    captains_text += f"▪ Team1 Captain: {team_1_captain.mention} @{team_1_captain.name}\n"
    captains_text += f"▪ Team2 Captain: {team_2_captain.mention} @{team_2_captain.name}"
    embed.add_field(name="👑 Team Captains", value=captains_text, inline=False)
    
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    embed.add_field(name="👤 Created By", value=interaction.user.mention, inline=False)
    
    # Add poster image if available
    if poster_image:
        try:
            with open(poster_image, 'rb') as f:
                file = discord.File(f, filename="event_poster.png")
                embed.set_image(url="attachment://event_poster.png")
        except Exception as e:
            print(f"Error loading poster image: {e}")
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    # Create Take Schedule button
    take_schedule_view = TakeScheduleButton(event_id, team_1_captain, team_2_captain, interaction.channel)
    
    # Send confirmation to user
    await interaction.followup.send("✅ Event created and posted to both channels! Reminder will ping captains 10 minutes before start.", ephemeral=True)
    
    # Post in Take-Schedule channel (with button)
    try:
        schedule_channel = interaction.guild.get_channel(CHANNEL_IDS["take_schedule"])
        if schedule_channel:
            judge_ping = f"<@&{ROLE_IDS['judge']}>"
            if poster_image:
                with open(poster_image, 'rb') as f:
                    file = discord.File(f, filename="event_poster.png")
                    schedule_message = await schedule_channel.send(content=judge_ping, embed=embed, file=file, view=take_schedule_view)
            else:
                schedule_message = await schedule_channel.send(content=judge_ping, embed=embed, view=take_schedule_view)
            
            # Store the message ID for later deletion
            scheduled_events[event_id]['schedule_message_id'] = schedule_message.id
            scheduled_events[event_id]['schedule_channel_id'] = schedule_channel.id
        else:
            await interaction.followup.send("⚠️ Could not find Take-Schedule channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in Take-Schedule channel: {e}", ephemeral=True)
    
    # Post in the channel where command was used (without button)
    try:
        if poster_image:
            with open(poster_image, 'rb') as f:
                file = discord.File(f, filename="event_poster.png")
                await interaction.channel.send(embed=embed, file=file)
        else:
            await interaction.channel.send(embed=embed)

        # Schedule the 10-minute reminder
        await schedule_ten_minute_reminder(event_id, team_1_captain, team_2_captain, None, interaction.channel, event_datetime)
        
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in current channel: {e}", ephemeral=True)

@tree.command(name="event-result", description="Add event results (Head Organizer/Judge only)")
@app_commands.describe(
    winner="Winner of the event",
    winner_score="Winner's score",
    loser="Loser of the event", 
    loser_score="Loser's score",
    tournament="Tournament name (e.g., The Zumwalt S2)",
    round="Round name (e.g., Semi-Final, Final, Quarter-Final)",
    group="Group assignment (A-J) - optional",
    remarks="Remarks about the match (e.g., ggwp, close match)",
    ss_1="Screenshot 1 (upload)",
    ss_2="Screenshot 2 (upload)",
    ss_3="Screenshot 3 (upload)",
    ss_4="Screenshot 4 (upload)",
    ss_5="Screenshot 5 (upload)",
    ss_6="Screenshot 6 (upload)",
    ss_7="Screenshot 7 (upload)",
    ss_8="Screenshot 8 (upload)",
    ss_9="Screenshot 9 (upload)",
    ss_10="Screenshot 10 (upload)",
    ss_11="Screenshot 11 (upload)"
)
@app_commands.choices(
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def event_result(
    interaction: discord.Interaction,
    winner: discord.Member,
    winner_score: int,
    loser: discord.Member,
    loser_score: int,
    tournament: str,
    round: str,
    group: app_commands.Choice[str] = None,
    remarks: str = "ggwp",
    ss_1: discord.Attachment = None,
    ss_2: discord.Attachment = None,
    ss_3: discord.Attachment = None,
    ss_4: discord.Attachment = None,
    ss_5: discord.Attachment = None,
    ss_6: discord.Attachment = None,
    ss_7: discord.Attachment = None,
    ss_8: discord.Attachment = None,
    ss_9: discord.Attachment = None,
    ss_10: discord.Attachment = None,
    ss_11: discord.Attachment = None
):
    """Adds results for an event"""
    
    # Defer the response immediately to avoid timeout issues
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions
    if not has_event_result_permission(interaction):
        await interaction.followup.send("❌ You need **Head Organizer** or **Judge** role to post event results.", ephemeral=True)
        return

    # Validate scores
    if winner_score < 0 or loser_score < 0:
        await interaction.followup.send("❌ Scores cannot be negative", ephemeral=True)
        return
    
    # Resolve group label from choice
    group_label = group.value if group and isinstance(group, app_commands.Choice) else None
            
    # Create results embed matching the exact template format
    embed_description = f"🗓️ {winner.display_name} Vs {loser.display_name}\n"
    embed_description += f"**Tournament:** {tournament}\n"
    embed_description += f"**Round:** {round}"
    
    # Add group if specified
    if group_label:
        embed_description += f"\n**Group:** {group_label}"
    
    embed = discord.Embed(
        title="Results",
        description=embed_description,
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    # Captains Section
    captains_text = f"**Captains**\n"
    captains_text += f"▪ Team1 Captain: {winner.mention} `@{winner.name}`\n"
    captains_text += f"▪ Team2 Captain: {loser.mention} `@{loser.name}`"
    embed.add_field(name="", value=captains_text, inline=False)
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Results Section
    results_text = f"**Results**\n"
    results_text += f"🏆 {winner.display_name} ({winner_score}) Vs ({loser_score}) {loser.display_name} 💀"
    embed.add_field(name="", value=results_text, inline=False)
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Staff Section
    staff_text = f"👨‍⚖️ **Staffs**\n"
    staff_text += f"▪ Judge: {interaction.user.mention} `@{interaction.user.name}`"
    embed.add_field(name="", value=staff_text, inline=False)
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Remarks Section
    embed.add_field(name="📝 Remarks", value=remarks, inline=False)
    
    # Handle screenshots - collect them and send as files (no image embeds)
    screenshots = [ss_1, ss_2, ss_3, ss_4, ss_5, ss_6, ss_7, ss_8, ss_9, ss_10, ss_11]
    files_to_send = []
    screenshot_names = []
    
    for i, screenshot in enumerate(screenshots, 1):
        if screenshot:
            # Create a file object for each screenshot
            try:
                file_data = await screenshot.read()
                file_obj = discord.File(
                    fp=io.BytesIO(file_data),
                    filename=f"SS-{i}_{screenshot.filename}"
                )
                files_to_send.append(file_obj)
                screenshot_names.append(f"SS-{i}")
            except Exception as e:
                print(f"Error processing screenshot {i}: {e}")
    
    # Add screenshot section if any screenshots were provided
    if screenshot_names:
        screenshot_text = f"**Screenshots of Result ({len(screenshot_names)} images)**\n"
        screenshot_text += f"📷 {' • '.join(screenshot_names)}"
        embed.add_field(name="", value=screenshot_text, inline=False)
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    # Send confirmation to user
    await interaction.followup.send("✅ Event results posted to Results channel, current channel, and Staff Attendance logged!", ephemeral=True)
    
    # Post in Results channel with screenshots as attachments
    results_posted = False
    try:
        results_channel = interaction.guild.get_channel(CHANNEL_IDS["results"])
        if results_channel:
            if files_to_send:
                # Create copies of files for results channel (files can only be used once)
                results_files = []
                for file_obj in files_to_send:
                    file_obj.fp.seek(0)  # Reset file pointer
                    file_data = file_obj.fp.read()
                    results_files.append(discord.File(
                        fp=io.BytesIO(file_data),
                        filename=file_obj.filename
                    ))
                await results_channel.send(embed=embed, files=results_files)
            else:
                await results_channel.send(embed=embed)
            results_posted = True
        else:
            await interaction.followup.send("⚠️ Could not find Results channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in Results channel: {e}", ephemeral=True)
    
    # Post in current channel (where command was executed)
    try:
        current_channel = interaction.channel
        if current_channel and current_channel.id != CHANNEL_IDS["results"]:  # Don't duplicate if already in results channel
            if files_to_send:
                # Reset file pointers and create new file objects for current channel
                current_files = []
                for file_obj in files_to_send:
                    file_obj.fp.seek(0)  # Reset file pointer
                    file_data = file_obj.fp.read()
                    current_files.append(discord.File(
                        fp=io.BytesIO(file_data),
                        filename=file_obj.filename
                    ))
                await current_channel.send(embed=embed, files=current_files)
            else:
                await current_channel.send(embed=embed)
        elif current_channel and current_channel.id == CHANNEL_IDS["results"] and not results_posted:
            # If we're in results channel but posting failed above, try again
            if files_to_send:
                await current_channel.send(embed=embed, files=files_to_send)
            else:
                await current_channel.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Could not post in current channel: {e}", ephemeral=True)

    # Winner-only summary removed per request
    
    # Post staff attendance in Staff Attendance channel
    try:
        staff_attendance_channel = interaction.guild.get_channel(CHANNEL_IDS["staff_attendance"])
        if staff_attendance_channel:
            # Create staff attendance message
            attendance_text = f"🏅 {winner.display_name} Vs {loser.display_name}\n"
            attendance_text += f"**Round :** {round}\n"
            
            # Add group if specified
            if group_label:
                attendance_text += f"**Group :** {group_label}\n"
            
            attendance_text += f"\n**Results**\n"
            attendance_text += f"🏆 {winner.display_name} ({winner_score}) Vs ({loser_score}) {loser.display_name} 💀\n\n"
            attendance_text += f"**Staffs**\n"
            attendance_text += f"• Judge: {interaction.user.mention} `@{interaction.user.name}`"
            
            await staff_attendance_channel.send(attendance_text)
        else:
            print("⚠️ Could not find Staff Attendance channel.")
    except Exception as e:
        print(f"⚠️ Could not post in Staff Attendance channel: {e}")

    # Update matching events with result data and schedule auto-cleanup
    try:
        current_channel_id = interaction.channel.id if interaction.channel else None
        matching_event_ids = []
        for ev_id, data in scheduled_events.items():
            if data.get('channel_id') == current_channel_id:
                # Match by captains to be safer
                try:
                    t1 = getattr(data.get('team1_captain'), 'id', None)
                    t2 = getattr(data.get('team2_captain'), 'id', None)
                    if winner.id in (t1, t2) and loser.id in (t1, t2):
                        matching_event_ids.append(ev_id)
                        
                        # Update the event with result data
                        scheduled_events[ev_id]['result_added'] = True
                        scheduled_events[ev_id]['result_winner'] = winner
                        scheduled_events[ev_id]['result_loser'] = loser
                        scheduled_events[ev_id]['result_winner_score'] = winner_score
                        scheduled_events[ev_id]['result_loser_score'] = loser_score
                        scheduled_events[ev_id]['result_judge'] = interaction.user
                        scheduled_events[ev_id]['result_group'] = group_label
                        scheduled_events[ev_id]['result_remarks'] = remarks
                        
                        print(f"Updated event {ev_id} with result data")
                except Exception as e:
                    print(f"Error updating event {ev_id}: {e}")
                    matching_event_ids.append(ev_id)
        
        # Save updated events
        if matching_event_ids:
            save_scheduled_events()

        scheduled_any = False
        for ev_id in matching_event_ids:
            # Update the original schedule message title with checkmark
            try:
                event_data = scheduled_events.get(ev_id)
                if event_data:
                    schedule_channel_id = event_data.get('schedule_channel_id')
                    schedule_message_id = event_data.get('schedule_message_id')
                    
                    if schedule_channel_id and schedule_message_id:
                        schedule_channel = interaction.guild.get_channel(schedule_channel_id)
                        if schedule_channel:
                            try:
                                schedule_message = await schedule_channel.fetch_message(schedule_message_id)
                                if schedule_message.embeds:
                                    embed = schedule_message.embeds[0]
                                    # Update title with checkmark
                                    if update_embed_title_with_checkmark(embed):
                                        try:
                                            await schedule_message.edit(embed=embed)
                                            print(f"Updated schedule title with checkmark for event {ev_id}")
                                        except discord.Forbidden:
                                            print(f"Bot doesn't have permission to edit message in channel {schedule_channel.name}")
                                        except Exception as edit_error:
                                            print(f"Error editing schedule message for event {ev_id}: {edit_error}")
                            except discord.NotFound:
                                print(f"Schedule message not found for event {ev_id}")
                            except Exception as e:
                                print(f"Error updating schedule title for event {ev_id}: {e}")
            except Exception as e:
                print(f"Error processing title update for event {ev_id}: {e}")
            
            await schedule_event_cleanup(ev_id, delay_hours=36)
            scheduled_any = True
        
        # Also update any schedule messages in the current channel
        try:
            current_channel = interaction.channel
            if current_channel:
                # Look for recent messages in current channel that might be schedule messages
                async for message in current_channel.history(limit=50):
                    if message.embeds and message.author == bot.user:
                        embed = message.embeds[0]
                        # Check if this looks like a schedule message with green circle
                        if embed.title and embed.title.startswith("🟢"):
                            # Check if this matches our winner/loser
                            description = embed.description or ""
                            if (winner.display_name in description and loser.display_name in description) or \
                               (winner.mention in description and loser.mention in description):
                                if update_embed_title_with_checkmark(embed):
                                    try:
                                        await message.edit(embed=embed)
                                        print(f"Updated current channel schedule title with checkmark")
                                    except discord.Forbidden:
                                        print(f"Bot doesn't have permission to edit message in current channel")
                                    except Exception as edit_error:
                                        print(f"Error editing current channel message: {edit_error}")
                                break
        except Exception as e:
            print(f"Error updating current channel schedule title: {e}")

        if scheduled_any:
            await interaction.followup.send("🧹 Auto-cleanup scheduled: Related event(s) will be removed after 24 hours.", ephemeral=True)
    except Exception as e:
        print(f"Error scheduling auto-cleanup after results: {e}")

@tree.command(name="time", description="Get a random match time from fixed 30-min slots (12:00-17:00 UTC)")
async def time(interaction: discord.Interaction):
    """Pick a random time from 30-minute slots between 12:00 and 17:00 UTC and show all slots."""
    
    import random
    
    # Build fixed 30-minute slots from 12:00 to 17:00 (inclusive), excluding 17:30
    slots = [
        f"{hour:02d}:{minute:02d} UTC"
        for hour in range(12, 18)
        for minute in (0, 30)
        if not (hour == 17 and minute == 30)
    ]
    
    chosen_time = random.choice(slots)
    
    embed = discord.Embed(
        title="⏰ Match Time (30‑min slots)",
        description=f"**Your random match time:** {chosen_time}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
                    )
                                       
    embed.add_field(
        name="🕒 Range",
        value="From 12:00 to 17:00 UTC (every 30 minutes)",
        inline=False
    )
                    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    await interaction.response.send_message(embed=embed)

## Removed test-poster command per request

@tree.command(name="maps", description="Randomly select 3, 5, or 7 maps for gameplay")
@app_commands.describe(
    count="Number of maps to select (3, 5, or 7)"
)
async def maps(interaction: discord.Interaction, count: int):
    """Randomly selects 3, 5, or 7 maps from the available map pool"""
    
    import random
    
    # Predefined map list
    maps_list = [
        "New Storm (2024)",
        "Arid Frontier", 
        "Islands of Iceland",
        "Unexplored Rocks",
        "Arctic",
        "Lost City",
        "Polar Frontier",
        "Hidden Dragon",
        "Monstrous Maelstrom",
        "Two Samurai",
        "Stone Peaks",
        "Viking Bay",
        "Greenlands",
        "Old Storm"
    ]
    
    # Validate count
    if count not in [3, 5, 7]:
        await interaction.response.send_message("❌ Please select 3, 5, or 7 maps only.", ephemeral=True)
        return
    
    # Randomly select the specified number of maps
    selected_maps = random.sample(maps_list, count)
    
    embed = discord.Embed(
        title=f"🗺️ Random Map Selection {ORGANIZATION_NAME}",
        description=f"**Randomly selected {count} map(s):**",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add selected maps as a field
    selected_maps_text = "\n".join([f"• {map_name}" for map_name in selected_maps])
    embed.add_field(
        name=f"🎯 Selected Maps ({count})",
        value=selected_maps_text,
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="choose", description="Randomly choose from a list of options")
@app_commands.describe(
    options="List of options separated by commas"
)
async def choose(interaction: discord.Interaction, options: str):
    """Randomly selects one option from a comma-separated list"""
    
    import random
    
    # Handle comma-separated options (original functionality)
    option_list = [option.strip() for option in options.split(',') if option.strip()]
    
    # Validate input
    if len(option_list) < 2:
        await interaction.response.send_message("❌ Please provide at least 2 options separated by commas.", ephemeral=True)
        return
    
    if len(option_list) > 20:
        await interaction.response.send_message("❌ Too many options! Please provide 20 or fewer options.", ephemeral=True)
        return
    
    # Randomly select one option
    chosen_option = random.choice(option_list)
    
    # Create embed
    embed = discord.Embed(
        title="🎲 Random Choice",
        description=f"**Selected:** {chosen_option}",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add all options as a field
    options_text = "\n".join([f"• {option}" for option in option_list])
    embed.add_field(
        name=f"📋 Available Options ({len(option_list)})",
        value=options_text,
        inline=False
    )
    
    embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="unassigned_events", description="List events without a judge assigned (Bot Owner/Judges/Organizers)")
async def unassigned_events(interaction: discord.Interaction):
    """Show all scheduled events that do not currently have a judge assigned."""
    try:
        # Allow Bot Owner, Organizer, Bot Op, and Judges to view
        if interaction.user.id != BOT_OWNER_ID:
            organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"]) if interaction.user else None
            bot_op_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["bot_op"]) if interaction.user else None
            judge_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["judge"]) if interaction.user else None

            if not (organizer_role or bot_op_role or judge_role):
                await interaction.response.send_message("❌ You need **Bot Owner**, **Organizer** or **Judge** role to view unassigned events.", ephemeral=True)
                return

        # Build list of unassigned events
        unassigned = []
        for event_id, data in scheduled_events.items():
            if not data.get('judge'):
                unassigned.append((event_id, data))

        # If none, inform
        if not unassigned:
            await interaction.response.send_message("✅ All events currently have a judge assigned.", ephemeral=True)
            return

        # Sort by datetime if present
        try:
            unassigned.sort(key=lambda x: x[1].get('datetime') or datetime.datetime.max)
        except Exception:
            pass

        # Create embed summary
        embed = discord.Embed(
            title="📝 Unassigned Events",
            description="Events without a judge. Use the message link to take the schedule.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )

        # Add up to 25 entries (Discord practical limit for a single embed field block)
        lines = []
        for idx, (ev_id, data) in enumerate(unassigned[:25], start=1):
            round_label = data.get('round', 'Round')
            date_str = data.get('date_str', 'N/A')
            time_str = data.get('time_str', 'N/A')
            ch_id = data.get('schedule_channel_id') or data.get('channel_id')
            msg_id = data.get('schedule_message_id')
            team1 = data.get('team1_captain')
            team2 = data.get('team2_captain')
            team1_name = getattr(team1, 'display_name', 'Unknown') if team1 else 'Unknown'
            team2_name = getattr(team2, 'display_name', 'Unknown') if team2 else 'Unknown'

            link = None
            try:
                if interaction.guild and ch_id and msg_id:
                    link = f"https://discord.com/channels/{interaction.guild.id}/{ch_id}/{msg_id}"
            except Exception:
                link = None

            if link:
                line = f"{idx}. {team1_name} vs {team2_name} • {round_label} • {time_str} • {date_str}\n↪ {link}"
            else:
                line = f"{idx}. {team1_name} vs {team2_name} • {round_label} • {time_str} • {date_str}"
            lines.append(line)

        embed.add_field(
            name=f"Available ({len(unassigned)})",
            value="\n\n".join(lines),
            inline=False
        )

        embed.set_footer(text="Use the link to open the original schedule and press Take Schedule.")

        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        print(f"Error in unassigned_events: {e}")
        try:
            await interaction.response.send_message("❌ An error occurred while fetching unassigned events.", ephemeral=True)
        except Exception:
            pass

@tree.command(name="event-delete", description="Delete a scheduled event (Bot Admin/Organizer/Bot Op only)")
async def event_delete(interaction: discord.Interaction):
    # Check permissions - Bot Owner, Organizer or Bot Op can delete events
    if interaction.user.id != BOT_OWNER_ID:
        organizer_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["organizer"])
        bot_op_role = discord.utils.get(interaction.user.roles, id=ROLE_IDS["bot_op"])
        
        if not (organizer_role or bot_op_role):
            await interaction.response.send_message("❌ You need **Bot Owner**, **Organizer** or **Bot Op** role to delete events.", ephemeral=True)
            return
    
    try:
        # Check if there are any scheduled events
        if not scheduled_events:
            await interaction.response.send_message(f"❌ No scheduled events found to delete.\n\n**Debug Info:**\n• Scheduled events count: {len(scheduled_events)}\n• Events in memory: {list(scheduled_events.keys()) if scheduled_events else 'None'}", ephemeral=True)
            return
        
        # Create dropdown with event names
        class EventDeleteView(View):
            def __init__(self):
                super().__init__(timeout=60)
                
            @discord.ui.select(
                placeholder="Select an event to delete...",
                options=[
                    discord.SelectOption(
                        label=f"{event_data.get('team1_captain').display_name if event_data.get('team1_captain') else 'Unknown'} VS {event_data.get('team2_captain').display_name if event_data.get('team2_captain') else 'Unknown'}",
                        description=f"{event_data.get('round', 'Unknown Round')} - {event_data.get('date_str', 'No date')} at {event_data.get('time_str', 'No time')}",
                        value=event_id
                    )
                    for event_id, event_data in list(scheduled_events.items())[:25]  # Discord limit of 25 options
                ]
            )
            async def select_event(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                selected_event_id = select.values[0]
                
                # Get event details for confirmation
                event_data = scheduled_events[selected_event_id]
                
                # Cancel any scheduled reminders
                if selected_event_id in reminder_tasks:
                    reminder_tasks[selected_event_id].cancel()
                    del reminder_tasks[selected_event_id]
                
                # Remove judge assignment if exists
                if 'judge' in event_data and event_data['judge']:
                    judge_id = event_data['judge'].id
                    remove_judge_assignment(judge_id, selected_event_id)
                
                # Delete the original schedule message if it exists
                deleted_message = False
                if 'schedule_message_id' in event_data and 'schedule_channel_id' in event_data:
                    try:
                        schedule_channel = select_interaction.guild.get_channel(event_data['schedule_channel_id'])
                        if schedule_channel:
                            schedule_message = await schedule_channel.fetch_message(event_data['schedule_message_id'])
                            await schedule_message.delete()
                            deleted_message = True
                    except discord.NotFound:
                        pass  # Message already deleted
                    except Exception as e:
                        print(f"Error deleting schedule message: {e}")
                
                # Clean up any temporary poster files
                if 'poster_path' in event_data:
                    try:
                        import os
                        if os.path.exists(event_data['poster_path']):
                            os.remove(event_data['poster_path'])
                    except Exception as e:
                        print(f"Error deleting poster file: {e}")
                
                # Remove from scheduled events
                del scheduled_events[selected_event_id]
                
                # Save events to file
                save_scheduled_events()
                
                # Create confirmation embed
                embed = discord.Embed(
                    title="🗑️ Event Deleted",
                    description=f"Event has been successfully deleted.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                
                embed.add_field(
                    name="📋 Deleted Event Details",
                    value=f"**Title:** {event_data.get('title', 'N/A')}\n**Round:** {event_data.get('round', 'N/A')}\n**Time:** {event_data.get('time_str', 'N/A')}\n**Date:** {event_data.get('date_str', 'N/A')}",
                    inline=False
                )
                
                # Build actions completed list
                actions_completed = [
                    "• Event removed from schedule",
                    "• Reminder cancelled",
                    "• Judge assignment cleared"
                ]
                
                if deleted_message:
                    actions_completed.append("• Original schedule message deleted")
                
                if 'poster_path' in event_data:
                    actions_completed.append("• Temporary poster file cleaned up")
                
                embed.add_field(
                    name="✅ Actions Completed",
                    value="\n".join(actions_completed),
                    inline=False
                )
                
                embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
                
                await select_interaction.response.edit_message(embed=embed, view=None)
        
        # Create initial embed
        embed = discord.Embed(
            title="🗑️ Delete Event",
            description="Select an event from the dropdown below to delete it.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Available Events",
            value=f"Found {len(scheduled_events)} scheduled event(s)",
            inline=False
        )
        
        embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
        
        view = EventDeleteView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(name="exchange_judge", description="Exchange an old judge for a new judge for event(s) in this channel")
@app_commands.describe(
    old_judge="The current judge to replace",
    new_judge="The new judge to assign"
)
async def exchange_judge(
    interaction: discord.Interaction,
    old_judge: discord.Member,
    new_judge: discord.Member
):
    # Only Head Helper or Helper Team can exchange judges
    if not has_event_create_permission(interaction):
        await interaction.response.send_message("❌ You need Head Organizer, Head Helper or Helper Team role to exchange judges.", ephemeral=True)
        return

    # Validate roles of old/new judges
    judge_role = discord.utils.get(interaction.guild.roles, id=ROLE_IDS["judge"]) if interaction.guild else None
    if judge_role:
        if judge_role not in old_judge.roles:
            await interaction.response.send_message("❌ Old judge does not have the Judge role.", ephemeral=True)
            return
        if judge_role not in new_judge.roles:
            await interaction.response.send_message("❌ New judge must have the Judge role.", ephemeral=True)
            return

    # Determine target events in the current channel
    target_event_ids = []
    current_channel_id = interaction.channel.id if interaction.channel else None
    for ev_id, data in scheduled_events.items():
        if data.get('channel_id') == current_channel_id and data.get('judge') and getattr(data.get('judge'), 'id', None) == old_judge.id:
            target_event_ids.append(ev_id)

    if not target_event_ids:
        await interaction.response.send_message("⚠️ No events in this channel are assigned to the old judge.", ephemeral=True)
        return

    # Perform exchange
    updated_count = 0
    for ev_id in target_event_ids:
        data = scheduled_events.get(ev_id)
        if not data:
            continue
        # Update event's judge
        data['judge'] = new_judge

        # Update judge_assignments mapping
        try:
            remove_judge_assignment(old_judge.id, ev_id)
        except Exception:
            pass
        add_judge_assignment(new_judge.id, ev_id)

        # Judge assigned successfully (reminder system removed)

        # Handle channel permissions and send notification to the event channel
        try:
            if interaction.guild and data.get('channel_id'):
                channel = interaction.guild.get_channel(data['channel_id'])
                if channel:
                    # Remove old judge from channel
                    await channel.set_permissions(old_judge, overwrite=None)
                    
                    # Add new judge to channel
                    await channel.set_permissions(
                        new_judge, 
                        read_messages=True, 
                        send_messages=True, 
                        view_channel=True,
                        embed_links=True,
                        attach_files=True,
                        read_message_history=True
                    )
                    
                    embed = discord.Embed(
                        title="🔁 Judge Exchanged",
                        description=(
                            f"**Old judge:** {old_judge.mention} `@{old_judge.name}`\n"
                            f"**New judge:** {new_judge.mention} `@{new_judge.name}`"
                        ),
                        color=discord.Color.purple(),
                        timestamp=discord.utils.utcnow()
                    )
                    channel_mention = channel.mention if channel else ""
                    embed.add_field(
                        name="📋 Event",
                        value=f"{channel_mention} • Time: {data.get('time_str', '')} • {data.get('round', '')}",
                        inline=False
                    )
                    embed.add_field(
                        name="🔐 Channel Access",
                        value=f"❌ **{old_judge.display_name}** removed from channel\n✅ **{new_judge.display_name}** added to channel",
                        inline=False
                    )
                    await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Error: Bot doesn't have permission to manage channel permissions for {ev_id}")
        except Exception as e:
            print(f"Failed to send judge exchange notification for {ev_id}: {e}")

        updated_count += 1

    await interaction.response.send_message(f"✅ Judge exchanged for {updated_count} event(s) in {interaction.channel.mention}.", ephemeral=True)


@tree.command(name="event-edit", description="Edit the event in this ticket channel (Bot Admin/Organizer/Bot Op only)")
@app_commands.describe(
    team_1_captain="Captain of team 1 (optional)",
    team_2_captain="Captain of team 2 (optional)", 
    hour="Hour of the event (0-23) (optional)",
    minute="Minute of the event (0-59) (optional)",
    date="Date of the event (optional)",
    month="Month of the event (optional)",
    round="Round label (optional)",
    tournament="Tournament name (optional)",
    group="Group assignment (A-J) or Winner/Loser (optional)"
)
@app_commands.choices(
    round=[
        app_commands.Choice(name="R1", value="R1"),
        app_commands.Choice(name="R2", value="R2"),
        app_commands.Choice(name="R3", value="R3"),
        app_commands.Choice(name="R4", value="R4"),
        app_commands.Choice(name="R5", value="R5"),
        app_commands.Choice(name="R6", value="R6"),
        app_commands.Choice(name="R7", value="R7"),
        app_commands.Choice(name="R8", value="R8"),
        app_commands.Choice(name="R9", value="R9"),
        app_commands.Choice(name="R10", value="R10"),
        app_commands.Choice(name="Qualifier", value="Qualifier"),
        app_commands.Choice(name="Semi Final", value="Semi Final"),
        app_commands.Choice(name="Final", value="Final"),
    ],
    group=[
        app_commands.Choice(name="Group A", value="Group A"),
        app_commands.Choice(name="Group B", value="Group B"),
        app_commands.Choice(name="Group C", value="Group C"),
        app_commands.Choice(name="Group D", value="Group D"),
        app_commands.Choice(name="Group E", value="Group E"),
        app_commands.Choice(name="Group F", value="Group F"),
        app_commands.Choice(name="Group G", value="Group G"),
        app_commands.Choice(name="Group H", value="Group H"),
        app_commands.Choice(name="Group I", value="Group I"),
        app_commands.Choice(name="Group J", value="Group J"),
        app_commands.Choice(name="Winner", value="Winner"),
        app_commands.Choice(name="Loser", value="Loser"),
    ]
)
async def event_edit(
    interaction: discord.Interaction,
    team_1_captain: discord.Member = None,
    team_2_captain: discord.Member = None,
    hour: int = None,
    minute: int = None,
    date: int = None,
    month: int = None,
    round: app_commands.Choice[str] = None,
    tournament: str = None,
    group: app_commands.Choice[str] = None
):
    """Edit the event in this ticket channel"""
    
    # Defer the response to give us more time for processing
    await interaction.response.defer(ephemeral=True)
    
    # Check permissions - Bot Owner, Head Organizer, Head Helper or Helper Team can edit events
    if interaction.user.id != BOT_OWNER_ID:
        if not has_event_create_permission(interaction):
            await interaction.followup.send("❌ You need **Bot Owner**, **Head Organizer**, **Head Helper** or **Helper Team** role to edit events.", ephemeral=True)
            return
    
    # Find event in current channel
    current_channel_id = interaction.channel.id
    event_to_edit = None
    event_id = None
    
    for ev_id, event_data in scheduled_events.items():
        if event_data.get('channel_id') == current_channel_id:
            event_to_edit = event_data
            event_id = ev_id
            break
    
    if not event_to_edit:
        await interaction.followup.send("❌ No event found in this ticket channel. Use `/event-create` to create an event first.", ephemeral=True)
        return
    
    # Check if at least one field is provided
    if not any([team_1_captain, team_2_captain, hour is not None, minute is not None, date is not None, month is not None, round, tournament, group]):
        await interaction.followup.send("❌ Please provide at least one field to update.", ephemeral=True)
        return
    
    # Validate input parameters only if provided
    if hour is not None and not (0 <= hour <= 23):
        await interaction.followup.send("❌ Hour must be between 0 and 23", ephemeral=True)
        return
    
    if date is not None and not (1 <= date <= 31):
        await interaction.followup.send("❌ Date must be between 1 and 31", ephemeral=True)
        return

    if month is not None and not (1 <= month <= 12):
        await interaction.followup.send("❌ Month must be between 1 and 12", ephemeral=True)
        return
            
    if minute is not None and not (0 <= minute <= 59):
        await interaction.followup.send("❌ Minute must be between 0 and 59", ephemeral=True)
        return

    try:
        # Get current event data
        current_datetime = event_to_edit.get('datetime', datetime.datetime.now())
        current_hour = hour if hour is not None else current_datetime.hour
        current_minute = minute if minute is not None else current_datetime.minute
        current_date = date if date is not None else current_datetime.day
        current_month = month if month is not None else current_datetime.month
        
        # Create new datetime
        current_year = datetime.datetime.now().year
        new_datetime = datetime.datetime(current_year, current_month, current_date, current_hour, current_minute)
        
        # Calculate time differences
        time_info = calculate_time_difference(new_datetime)
        
        # Update only provided fields
        if team_1_captain:
            event_to_edit['team1_captain'] = team_1_captain
        if team_2_captain:
            event_to_edit['team2_captain'] = team_2_captain
        if hour is not None or minute is not None or date is not None or month is not None:
            event_to_edit['datetime'] = new_datetime
            event_to_edit['time_str'] = time_info['utc_time']
            event_to_edit['date_str'] = f"{current_date:02d}/{current_month:02d}"
            event_to_edit['minutes_left'] = time_info['minutes_remaining']
        if round:
            round_label = round.value if isinstance(round, app_commands.Choice) else str(round)
            event_to_edit['round'] = round_label
        if tournament:
            event_to_edit['tournament'] = tournament
        if group:
            event_to_edit['group'] = group.value
        
        # Save updated events
        save_scheduled_events()
        
        # Schedule the 10-minute reminder with updated event data
        try:
            # Use the updated captains from the event data (which now contains the new values)
            await schedule_ten_minute_reminder(event_id, event_to_edit.get('team1_captain'), event_to_edit.get('team2_captain'), event_to_edit.get('judge'), interaction.channel, new_datetime)
        except Exception as e:
            print(f"Error scheduling reminder for updated event {event_id}: {e}")
        
        # Get updated event details for public posting
        team1_captain = event_to_edit.get('team1_captain')
        team2_captain = event_to_edit.get('team2_captain')
        round_info = event_to_edit.get('round', 'Unknown')
        tournament_info = event_to_edit.get('tournament', 'Unknown')
        time_info_display = event_to_edit.get('time_str', 'Unknown')
        date_info_display = event_to_edit.get('date_str', 'Unknown')
        group_info = event_to_edit.get('group', '')
        
        # Create public embed for updated event (similar to event-create)
        embed = discord.Embed(
            title="📝 Event Updated",
            description=f"**Event has been updated by {interaction.user.mention}**",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        # Event Details Section
        embed.add_field(
            name="📋 Updated Event Details", 
            value=f"**Team 1 Captain:** {team1_captain.mention if team1_captain else 'Unknown'} `@{team1_captain.name if team1_captain else 'Unknown'}`\n"
                  f"**Team 2 Captain:** {team2_captain.mention if team2_captain else 'Unknown'} `@{team2_captain.name if team2_captain else 'Unknown'}`\n\n"
                  f"**UTC Time:** {time_info_display}\n"
                  f"**Local Time:** <t:{int(new_datetime.timestamp())}:F> (<t:{int(new_datetime.timestamp())}:R>)\n\n"
                  f"**Round:** {round_info}\n"
                  f"**Tournament:** {tournament_info}\n\n"
                  f"**Channel:** {interaction.channel.mention}",
            inline=False
        )
        
        # Add spacing
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        if group_info:
            embed.add_field(
                name="🏆 Group Assignment",
                value=f"**Group:** {group_info}",
                inline=False
            )
        
        # Captains Section
        captains_text = f"**Captains**\n"
        captains_text += f"▪ Team1 Captain: {team1_captain.mention if team1_captain else 'Unknown'} `@{team1_captain.name if team1_captain else 'Unknown'}`\n"
        captains_text += f"▪ Team2 Captain: {team2_captain.mention if team2_captain else 'Unknown'} `@{team2_captain.name if team2_captain else 'Unknown'}`"
        embed.add_field(name="", value=captains_text, inline=False)
        
        embed.set_footer(text=f"Powered by • {ORGANIZATION_NAME}")
        
        # Post the updated event embed to the channel
        try:
            await interaction.channel.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Could not post in current channel: {e}", ephemeral=True)
        
        # Send confirmation to user
        await interaction.followup.send("✅ Event updated successfully!", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error updating event: {str(e)}", ephemeral=True)


# Ticket Management Commands - Removed as requested

@tree.command(name="general_tie_breaker", description="To break a tie between two teams using the highest total score")
@app_commands.describe(
    tm1_name="Name of the first team. By default, it is Alpha",
    tm1_pl1_score="Score of the first player of the first team",
    tm1_pl2_score="Score of the second player of the first team", 
    tm1_pl3_score="Score of the third player of the first team",
    tm1_pl4_score="Score of the fourth player of the first team",
    tm1_pl5_score="Score of the fifth player of the first team",
    tm2_name="Name of the second team. By default, it is Bravo",
    tm2_pl1_score="Score of the first player of the second team",
    tm2_pl2_score="Score of the second player of the second team",
    tm2_pl3_score="Score of the third player of the second team",
    tm2_pl4_score="Score of the fourth player of the second team",
    tm2_pl5_score="Score of the fifth player of the second team"
)
async def general_tie_breaker(
    interaction: discord.Interaction,
    tm1_pl1_score: int,
    tm1_pl2_score: int,
    tm1_pl3_score: int,
    tm1_pl4_score: int,
    tm1_pl5_score: int,
    tm2_pl1_score: int,
    tm2_pl2_score: int,
    tm2_pl3_score: int,
    tm2_pl4_score: int,
    tm2_pl5_score: int,
    tm1_name: str = "Alpha",
    tm2_name: str = "Bravo"
):
    """Break a tie between two teams using the highest total score"""
    
    # Check permissions - only organizers and helpers can use this command
    if not has_event_create_permission(interaction):
        await interaction.response.send_message("❌ You need **Organizers** or **Helpers Tournament** role to use tie breaker.", ephemeral=True)
        return
    
    # Calculate team totals
    tm1_total = tm1_pl1_score + tm1_pl2_score + tm1_pl3_score + tm1_pl4_score + tm1_pl5_score
    tm2_total = tm2_pl1_score + tm2_pl2_score + tm2_pl3_score + tm2_pl4_score + tm2_pl5_score
    
    # Determine winner
    if tm1_total > tm2_total:
        winner = tm1_name
        winner_total = tm1_total
        loser = tm2_name
        loser_total = tm2_total
        color = discord.Color.green()
    elif tm2_total > tm1_total:
        winner = tm2_name
        winner_total = tm2_total
        loser = tm1_name
        loser_total = tm1_total
        color = discord.Color.green()
    else:
        # Still tied
        winner = "TIE"
        winner_total = tm1_total
        loser = ""
        loser_total = tm2_total
        color = discord.Color.orange()
    
    # Create result embed
    embed = discord.Embed(
        title="🏆 Tie Breaker Results",
        description="Results based on highest total team score",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    # Team 1 scores
    embed.add_field(
        name=f"🔵 {tm1_name} Team",
        value=f"Player 1: `{tm1_pl1_score}`\n"
              f"Player 2: `{tm1_pl2_score}`\n"
              f"Player 3: `{tm1_pl3_score}`\n"
              f"Player 4: `{tm1_pl4_score}`\n"
              f"Player 5: `{tm1_pl5_score}`\n"
              f"**Total: {tm1_total}**",
        inline=True
    )
    
    # Team 2 scores
    embed.add_field(
        name=f"🔴 {tm2_name} Team",
        value=f"Player 1: `{tm2_pl1_score}`\n"
              f"Player 2: `{tm2_pl2_score}`\n"
              f"Player 3: `{tm2_pl3_score}`\n"
              f"Player 4: `{tm2_pl4_score}`\n"
              f"Player 5: `{tm2_pl5_score}`\n"
              f"**Total: {tm2_total}**",
        inline=True
    )
    
    # Add spacing
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    
    # Result
    if winner == "TIE":
        embed.add_field(
            name="🤝 Final Result",
            value=f"**STILL TIED!**\n"
                  f"Both teams scored {tm1_total} points\n"
                  f"Additional tie-breaking method needed",
            inline=False
        )
    else:
        embed.add_field(
            name="🏆 Winner",
            value=f"**{winner}** wins the tie breaker!\n"
                  f"**{winner}**: {winner_total} points\n"
                  f"**{loser}**: {loser_total} points\n"
                  f"Difference: {abs(winner_total - loser_total)} points",
            inline=False
        )
    
    embed.set_footer(text=f"Tie Breaker • Calculated by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    # Get Discord token from environment
    token = os.environ.get("DISCORD_TOKEN")
    
    # Fallback method if direct get doesn't work
    if not token:
        for key, value in os.environ.items():
            if 'DISCORD' in key and 'TOKEN' in key:
                token = value
                break
    
    if not token:
        print("❌ Discord token not found in environment variables.")
        print("Please set your Discord bot token in the DISCORD_TOKEN environment variable.")
        print("You can also create a .env file with: DISCORD_TOKEN=your_token_here")
        exit(1)
    
    try:
        print("🚀 Starting Discord bot...")
        print("📡 Connecting to Discord...")
        bot.run(token, log_handler=None)  # Disable default logging to reduce startup time
    except discord.LoginFailure:
        print("❌ Invalid Discord token. Please check your bot token.")
        exit(1)
    except discord.HTTPException as e:
        print(f"❌ HTTP error connecting to Discord: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        exit(1)
