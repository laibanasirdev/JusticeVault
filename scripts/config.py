import os
from dotenv import load_dotenv
load_dotenv()
# The address from your terminal output
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x700b6A60ce7EaaEA56F065753d8dcB9653dbAD35")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# LangSmith observability (optional — tracing activates when both are set)
LANGCHAIN_API_KEY    = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_PROJECT    = os.getenv("LANGCHAIN_PROJECT", "justice-vault")
# Gets the directory where the script is, then goes up one level to the root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ABI_PATH = os.path.join(BASE_DIR, "out", "JusticeVault.sol", "JusticeVault.json")

# Local Anvil URL
RPC_URL = "http://127.0.0.1:8545"



IPFS_GATEWAY = "https://ipfs.io/ipfs/"
TEMP_DIR = os.path.join(BASE_DIR, "temp_legal_files")

# Ensure the temp directory exists
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Evidence feed for dashboard: Oracle writes integrity + AI summary here
FEED_PATH = os.path.join(BASE_DIR, "evidence_feed.json")