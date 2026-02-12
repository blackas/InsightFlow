import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Keywords for filtering relevant news
KEYWORDS = [
    "AI",
    "LLM",
    "GPT",
    "Gemini",
    "Claude",
    "transformer",
    "deep learning",
    "machine learning",
    "React",
    "TypeScript",
    "Rust",
    "Go",
    "Docker",
    "Kubernetes",
    "K8s",
    "DevOps",
    "CI/CD",
    "microservice",
    "API",
    "database",
    "PostgreSQL",
    "Redis",
    "cloud",
    "AWS",
    "GCP",
    "Azure",
    "serverless",
    "인공지능",
    "딥러닝",
    "머신러닝",
]

# RSS Feed URLs
GEEKNEWS_RSS_URL = "https://news.hada.io/rss/news"

# Hacker News API
HN_API_BASE = "https://hacker-news.firebaseio.com/v0/"

# Gemini Model
GEMINI_MODEL = "gemini-2.5-flash"

# Processing parameters
BATCH_SIZE = 8
HN_TOP_N = 30

# Relevance thresholds
RELEVANCE_THRESHOLD = 0.6
ISSUE_THRESHOLD = 0.8

# Notion Tags
NOTION_TAGS = [
    "AI/ML",
    "LLM",
    "Frontend",
    "Backend",
    "DevOps",
    "Database",
    "Cloud",
    "Security",
    "Language",
    "Tool",
    "Career",
    "Other",
]

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# TLDR AI Configuration
TLDR_AI_URL = "https://tldr.tech/api/latest/ai"
TLDR_SECTIONS = [
    "Headlines & Launches",
    "Deep Dives & Analysis",
    "Engineering & Research",
    "Miscellaneous",
    "Quick Links",
]

# Artificial Analysis Configuration
ARTIFICIAL_ANALYSIS_API_KEY = os.getenv("ARTIFICIAL_ANALYSIS_API_KEY")
ARTIFICIAL_ANALYSIS_API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"

# Model Tracker Configuration
MODEL_TRACKER_DB_PATH = "data/models.db"
MODEL_RANK_CHANGE_THRESHOLD = 10  # Top N rank changes
MODEL_PRICE_CHANGE_THRESHOLD = 0.10  # 10% price change threshold


def get_week_identifier() -> str:
    """
    Get the current week identifier in ISO format.

    Returns:
        str: ISO week identifier in format "YYYY-WNN" (e.g., "2026-W07")
    """
    year, week, _ = datetime.now().isocalendar()
    return f"{year:04d}-W{week:02d}"
