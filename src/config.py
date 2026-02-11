import os
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

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
