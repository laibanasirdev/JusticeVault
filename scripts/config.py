import os

# The address from your terminal output
CONTRACT_ADDRESS = "0x700b6A60ce7EaaEA56F065753d8dcB9653dbAD35"

# Gets the directory where the script is, then goes up one level to the root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ABI_PATH = os.path.join(BASE_DIR, "out", "JusticeVault.sol", "JusticeVault.json")

# Local Anvil URL
RPC_URL = "http://127.0.0.1:8545"


GEMINI_API_KEY = "AIzaSyBSjKLlshJeT_kYNi8IFAGK107rUv58DJA"
IPFS_GATEWAY = "https://ipfs.io/ipfs/"
TEMP_DIR = os.path.join(BASE_DIR, "temp_legal_files")

# Ensure the temp directory exists
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)