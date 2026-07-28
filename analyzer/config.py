import os
import warnings as python_warnings

from dotenv import load_dotenv

# Suppress gRPC and ALTS warnings emitted by google-generativeai
python_warnings.filterwarnings('ignore')
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash'
DEFAULT_INPUT_FILE = 'student_repo_list.csv'
DEFAULT_OUTPUT_DIR = 'output'
AI_CACHE_DIRNAME = '.ai_cache'
