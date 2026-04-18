from os import environ
from pathlib import Path

# BASE DIRECTORY
BASE_DIR = Path(__file__).resolve().parent

# DEBUG MODE (heroku specific)
PRODUCTION = environ.get('OTREE_PRODUCTION')
DEBUG = not PRODUCTION

num_participant = int(environ.get("NUM_PARTICIPANT", 7))

# -------------------
# SESSION CONFIGS
# -------------------
SESSION_CONFIGS = [
    dict(
        name = 'team_reasoning_llm_p_beauty',
        display_name = "team_reasoning_llm_p_beauty",
        num_demo_participants = 4 if DEBUG else num_participant,
        app_sequence = ['phase1', 'phase2', 'phase3', 'phase_AI','after_questionaire'],
    ),
]

SESSION_CONFIG_DEFAULTS = dict(
    display_name = "team_reasoning_llm_p_beauty",
    real_world_currency_per_point = 1.00,
    participation_fee = 150.00,
    doc="",
)

# -------------------
# LANGUAGE & CURRENCY
# -------------------
LANGUAGE_CODE = 'en'
REAL_WORLD_CURRENCY_CODE = 'TWD'
REAL_WORLD_CURRENCY_DECIMAL_PLACES = 0
USE_POINTS = False

# -------------------
# ADMIN
# -------------------
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get("OTREE_ADMIN_PASSWORD") or 'tassel'

# optional HTML for demo page
DEMO_PAGE_INTRO_HTML = ""

# SECRET_KEY required by Django
SECRET_KEY = environ.get("OTREE_SECRET_KEY") or 'replace-with-a-random-string'

# -------------------
# INSTALLED APPS
# -------------------
INSTALLED_APPS = ['otree']
