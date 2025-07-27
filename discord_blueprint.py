from flask import Blueprint
from flask_login import current_user
import asyncio
import random
import re

from discord_bot import MyBot

discord_bp = Blueprint('discord_api', __name__)
discord_bot = MyBot()

# Define the Discord channel ID where messages should be sent.
# In a real application, this should be loaded from a configuration file.
DISCORD_CHANNEL_ID = 1395241200310550653

def roll_100():
    """Rolls a 100-sided die."""
    return random.randint(1, 100)

def format_discord_roll_message(roll_type: str, roll: int, target_value: int) -> str:
    """
    Formats a standardized and visually appealing message for a d100 roll outcome.
    This function incorporates the specific success levels of Call of Cthulhu 7th Edition rules.
    Args:
        roll_type (str): The name of the roll (e.g., "STR", "Dodge", "Sanity Check").
        roll (int): The result of the d100 roll.
        target_value (int): The value the roll needed to be under or equal to for success.
    Returns:
        str: A formatted string ready to be sent to Discord, using Discord's markdown.
    """
    outcome = ""
    # Determine success or failure based on CoC rules.
    if roll <= target_value:
        # A roll of 1 is always a critical success.
        if roll == 1:

            outcome = "Critical Success"
        # A roll less than or equal to 1/5th of the skill is an Extreme Success.
        elif roll <= (target_value // 5):

            outcome = "Extreme Success"
        # A roll less than or equal to 1/2 of the skill is a Hard Success.
        elif roll <= (target_value // 2):

            outcome = "Hard Success"
        else:

            outcome = "Regular Success"
    else:
        # Determine if the failure is a "fumble" based on standard CoC rules.
        if (target_value < 50 and roll >= 96) or (target_value >= 50 and roll == 100):

            outcome = "Fumble"
        else:

            outcome = "Failure"

    # Assemble the message using Discord markdown for clarity and visual appeal.
    message = (
        f"**{current_user.username} rolled a ---**\n"
        f"**{roll_type} Roll**\n"
        f"Rolled: `{roll}`\n"
        f"Target: `{target_value}`\n"
        f"Outcome: **{outcome}**"
    )
    return message

def send_discord_message(message: str):
    """
    Safely sends a message to Discord from a synchronous Flask thread.
    """
    try:
        asyncio.run_coroutine_threadsafe(
            discord_bot.send_message(DISCORD_CHANNEL_ID, message),
            discord_bot.loop
        )
    except Exception as e:
        print(f"Error sending Discord message: {e}")



@discord_bp.route('/<string:stat_name>/<int:stat_value>', methods=["POST"])
def discord_stat_roll(stat_name: str, stat_value: int) -> str:
    """
    Handles POST requests from HTMX for rolling against a specific character stat.
    The stat name (e.g., 'str', 'dex') and its integer value are extracted
    directly from the URL path.
    """
    print(f"API HIT: /stat/{stat_name}/{stat_value}")
    roll = roll_100()
    message = format_discord_roll_message(f"{stat_name.upper()} Check", roll, stat_value)
    send_discord_message(message)
    return ""


@discord_bp.route('/skill/<string:skill_name>/<int:skill_value>', methods=["POST"])
def roll_skill(skill_name: str, skill_value: int):
    """API endpoint for a generic skill check."""
    print(f"API HIT: /skill/{skill_name}/{skill_value}")
    roll = roll_100()
    # Format the display name, e.g., "ArtCraft" -> "Art Craft" or "OwnLanguage" -> "Own Language"
    display_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', skill_name)

    message = format_discord_roll_message(f"{display_name} Skill", roll, skill_value)
    send_discord_message(message)

    # hx-swap="none" means we don't need to return any HTML content.
    return ""


@discord_bp.route('/sanity_check/<int:sanity_value>', methods=["POST"])
def roll_sanity(sanity_value: int):
    """
    API endpoint for a Sanity roll. This is typically rolled against current sanity points.
    """
    print(f"API HIT: /sanity_check/{sanity_value}")
    roll = roll_100()

    message = format_discord_roll_message("Sanity Roll", roll, sanity_value)
    send_discord_message(message)

    return ""


@discord_bp.route('/luck_roll/<int:luck_value>', methods=["POST"])
def roll_luck(luck_value: int):
    """API endpoint for a Luck roll against the character's current Luck points."""
    print(f"API HIT: /luck_roll/{luck_value}")
    roll = roll_100()

    message = format_discord_roll_message("Luck Roll", roll, luck_value)
    send_discord_message(message)

    return ""

