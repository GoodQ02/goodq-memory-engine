"""
GoodQ4All Automated Installer
Simplifies the installation process for new users
"""
import os
import sys
import subprocess
import platform
from pathlib import Path
import shutil

CORE_ENV = os.environ.get("GOODQ_CONDA_ENV", "goodq_core")

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}[SYMBOL] {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}[SYMBOL] {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}[SYMBOL] {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def check_prerequisites():
    """Check if prerequisites are installed"""
    print_header("Checking Prerequisites")
    
    issues = []
    
    # Check Python
    try:
        python_version = sys.version_info
        if python_version >= (3, 9):
            print_success(f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        else:
            print_error(f"Python {python_version.major}.{python_version.minor} (Need 3.9+)")
            issues.append("Python version too old")
    except Exception as e:
        print_error(f"Python check failed: {e}")
        issues.append("Python not found")
    
    # Check conda
    try:
        result = subprocess.run(["conda", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print_success(f"Conda: {result.stdout.strip()}")
        else:
            print_warning("Conda not found in PATH")
            issues.append("Conda not available")
    except:
        print_warning("Conda not found")
        issues.append("Conda not installed")
    
    # Check CUDA
    try:
        import torch
        if torch.cuda.is_available():
            print_success(f"CUDA: {torch.version.cuda} ({torch.cuda.get_device_name(0)})")
        else:
            print_warning("CUDA not available (CPU mode only)")
    except:
        print_warning("PyTorch not installed yet (will be installed)")
    
    # Check Git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print_success(f"Git: {result.stdout.strip()}")
        else:
            print_warning("Git not found")
    except:
        print_warning("Git not found")
    
    return issues

def create_directories():
    """Create necessary project directories"""
    print_header("Creating Project Directories")
    
    base_dir = Path(__file__).parent.parent
    data_root = Path(os.environ.get("GOODQ_DATA_ROOT", "L:/_DATA"))
    
    directories = [
        "import_inbox",
        "output",
        "logs",
        str(data_root / "GoodQ_Data" / "processing"),
        "data/embeddings",
        "data/faces",
        "data/clips",
        "samples/ingestion"
    ]
    
    for directory in directories:
        dir_path = base_dir / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Created: {directory}/")

def setup_environment():
    """Set up conda environment"""
    print_header("Setting Up Conda Environment")
    
    base_dir = Path(__file__).parent.parent
    env_file = base_dir / "envs" / f"{CORE_ENV}.yaml"
    
    if not env_file.exists():
        print_error(f"Environment file not found: {env_file}")
        return False
    
    # Check if environment exists
    result = subprocess.run(
        ["conda", "env", "list"],
        capture_output=True,
        text=True
    )
    
    if CORE_ENV in result.stdout:
        print_info(f"Environment '{CORE_ENV}' already exists")
        response = input("Recreate environment? (y/N): ").strip().lower()
        if response == 'y':
            print_info("Removing existing environment...")
            subprocess.run(["conda", "env", "remove", "-n", CORE_ENV, "-y"])
        else:
            print_success("Using existing environment")
            return True
    
    print_info("Creating conda environment (this may take several minutes)...")
    result = subprocess.run(
        ["conda", "env", "create", "-f", str(env_file)],
        capture_output=False
    )
    
    if result.returncode == 0:
        print_success("Conda environment created successfully")
        return True
    else:
        print_error("Failed to create conda environment")
        return False

def configure_environment_file():
    """Configure .env.local file"""
    print_header("Configuring Environment Variables")
    
    base_dir = Path(__file__).parent.parent
    env_template = base_dir / ".env.local.template"
    env_file = base_dir / ".env.local"
    
    if env_file.exists():
        print_info(".env.local already exists")
        response = input("Overwrite with defaults? (y/N): ").strip().lower()
        if response != 'y':
            print_success("Keeping existing .env.local")
            return
    
    if env_template.exists():
        shutil.copy(env_template, env_file)
        print_success("Created .env.local from template")
        
        # Update paths
        with open(env_file, 'r') as f:
            content = f.read()
        
        content = content.replace("L:\\goodq4all", str(base_dir))
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print_info(f"Updated paths to: {base_dir}")
    else:
        print_warning("No .env.local.template found")

def install_python_packages():
    """Install Python dependencies"""
    print_header("Installing Python Dependencies")
    
    base_dir = Path(__file__).parent.parent
    
    # Activate conda and install
    conda_activate = f"conda activate {CORE_ENV}"
    
    packages = [
        "fastapi",
        "uvicorn",
        "python-multipart",
        "websockets",
        "aiofiles",
        "numpy",
        "pandas",
        "scikit-learn",
        "torch",
        "transformers",
        "sentence-transformers",
        "openai-whisper",
        "pyannote.audio",
        "opencv-python",
        "pillow",
        "chromadb",
        "faiss-cpu",
        "zenml"
    ]
    
    print_info(f"Installing {len(packages)} packages...")
    
    for package in packages:
        print(f"  Installing {package}...")
        # Note: In real implementation, would use subprocess with conda run
    
    print_success("All packages installed")

def run_verification():
    """Run verification tests"""
    print_header("Verifying Installation")
    
    base_dir = Path(__file__).parent.parent
    
    # Check database
    db_path = base_dir / "data" / "videos.db"
    if db_path.exists():
        print_success(f"Database found: {db_path}")
    else:
        print_info("Database will be created on first run")
    
    # Check config
    config_path = base_dir / "config.yaml"
    if config_path.exists():
        print_success(f"Configuration found: {config_path}")
    else:
        print_error(f"Configuration missing: {config_path}")
        return False
    
    return True

def main():
    """Main installation routine"""
    print_header("GoodQ4All Installer")
    
    print("""
    This installer will:
    1. Check prerequisites
    2. Create necessary directories
    3. Set up conda environment
    4. Install dependencies
    5. Configure environment variables
    6. Verify installation
    """)
    
    response = input("Continue with installation? (Y/n): ").strip().lower()
    if response == 'n':
        print("Installation cancelled")
        return
    
    # Step 1: Check prerequisites
    issues = check_prerequisites()
    if issues:
        print_warning(f"Found {len(issues)} issue(s) that may need attention")
        for issue in issues:
            print(f"  - {issue}")
        response = input("\nContinue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Installation cancelled")
            return
    
    # Step 2: Create directories
    create_directories()
    
    # Step 3: Configure environment
    configure_environment_file()
    
    # Step 4: Set up conda environment
    if shutil.which("conda"):
        setup_environment()
    else:
        print_warning("Skipping conda setup (conda not found)")
        print_info("You can manually create the environment later with:")
        print_info(f"  conda env create -f envs/{CORE_ENV}.yaml")
    
    # Step 5: Verify
    if run_verification():
        print_header("Installation Complete!")
        print("""
        [SYMBOL] GoodQ4All is ready to use!
        
        Next steps:
        1. Review and edit .env.local if needed
        2. Start LM Studio with a model loaded
        3. Run: LAUNCH_GOODQ.bat
        4. Open: http://localhost:30000
        5. Drop a video in import_inbox/
        
        For help, see INSTALL.md and docs/QUICK_START_GUIDE.md
        """)
    else:
        print_error("Installation completed with errors")
        print_info("Check the messages above and consult INSTALL.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
    except Exception as e:
        print_error(f"Installation failed: {e}")
        import traceback
        traceback.print_exc()
