"""
Setup script for bankruptcy auction crawler
"""
import subprocess
import sys
import os


def install_requirements():
    """Install Python requirements"""
    print("Installing Python requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Python requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Python requirements: {e}")
        return False
    return True


def install_playwright():
    """Install Playwright browsers"""
    print("Installing Playwright browsers...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install"])
        print("✓ Playwright browsers installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Playwright browsers: {e}")
        return False
    return True


def create_directories():
    """Create necessary directories"""
    print("Creating directories...")
    
    directories = ["output", "logs"]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created directory: {directory}")
        else:
            print(f"✓ Directory already exists: {directory}")
            
    return True


def test_installation():
    """Test if installation was successful"""
    print("Testing installation...")
    
    try:
        # Test imports
        from crawler.browser_controller import BrowserController
        from crawler.data_extractor import DataExtractor
        from crawler.pagination_handler import PaginationHandler
        from crawler.data_storage import DataStorage
        print("✓ All modules can be imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import test failed: {e}")
        return False


def main():
    """Main setup function"""
    print("Setting up Bankruptcy Auction Crawler...")
    print("=" * 50)
    
    success = True
    
    # Create directories
    if not create_directories():
        success = False
        
    # Install requirements
    if not install_requirements():
        success = False
        
    # Install Playwright
    if not install_playwright():
        success = False
        
    # Test installation
    if success and not test_installation():
        success = False
        
    print("=" * 50)
    
    if success:
        print("✓ Setup completed successfully!")
        print("\nYou can now run the crawler:")
        print("  python main.py --preview    # Preview mode")
        print("  python main.py              # Full crawl")
        print("  python main.py --help       # Show all options")
    else:
        print("✗ Setup failed. Please check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()