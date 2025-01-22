import os
import re
import subprocess
import sys

def find_python_files(directory):
    """Recursively find all Python files in the given directory."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def extract_imports(file_path):
    """Extract all imported modules from the given Python file."""
    imports = set()
    import_pattern = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)')
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            match = import_pattern.match(line)
            if match:
                imports.add(match.group(1))
    return imports

def check_installed_packages(packages):
    """Check if the given packages are installed."""
    installed_packages = set()
    for package in packages:
        try:
            __import__(package)
            installed_packages.add(package)
        except ImportError:
            pass
    return installed_packages

def install_packages(packages):
    """Install the given packages using pip."""
    for package in packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        except subprocess.CalledProcessError as e:
            print(f"Failed to install package: {package}. Error: {e}")

def main():
    # Define the directory to scan
    directory = '.'

    # Find all Python files in the directory
    python_files = find_python_files(directory)

    # Extract all imported modules from the Python files
    all_imports = set()
    for file in python_files:
        all_imports.update(extract_imports(file))

    # Check which packages are already installed
    installed_packages = check_installed_packages(all_imports)

    # Find the packages that are not installed
    uninstalled_packages = all_imports - installed_packages

    # Install the uninstalled packages
    if uninstalled_packages:
        print(f"Installing packages: {', '.join(uninstalled_packages)}")
        install_packages(uninstalled_packages)
    else:
        print("All packages are already installed.")

if __name__ == '__main__':
    main()