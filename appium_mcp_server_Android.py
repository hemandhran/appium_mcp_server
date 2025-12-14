from mcp.server.fastmcp import FastMCP
import subprocess
import os
import time
import shutil
import platform
import requests
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from selenium.webdriver.common.by import By
import xml.etree.ElementTree as ET

# Initialize the MCP Server
mcp = FastMCP("UniversalAppiumHelper")

# Global driver to hold the session
driver = None


def get_android_sdk_root():
    """Auto-detects Android SDK location based on OS."""
    # 1. Check if user set the environment variable manually (Best Practice)
    if os.environ.get("ANDROID_HOME"):
        return os.environ.get("ANDROID_HOME")
    if os.environ.get("ANDROID_SDK_ROOT"):
        return os.environ.get("ANDROID_SDK_ROOT")

    # 2. Fallback to default locations
    system = platform.system()
    user_home = os.path.expanduser("~")

    if system == "Windows":
        # C:\Users\Name\AppData\Local\Android\Sdk
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
    elif system == "Darwin":  # macOS
        # /Users/Name/Library/Android/sdk
        return os.path.join(user_home, "Library", "Android", "sdk")
    elif system == "Linux":
        return os.path.join(user_home, "Android", "Sdk")

    return None


@mcp.tool()
def start_android_emulator(avd_name: str):
    """
    Starts a local Android Emulator (Cross-Platform).
    """
    sdk_root = get_android_sdk_root()
    if not sdk_root or not os.path.exists(sdk_root):
        return f"Error: Android SDK not found. Set ANDROID_HOME environment variable."

    # Emulator binary is usually in /emulator or /tools
    emulator_bin = os.path.join(sdk_root, "emulator", "emulator")
    if platform.system() == "Windows":
        emulator_bin += ".exe"

    if not os.path.exists(emulator_bin):
        # Fallback search using 'which'
        emulator_bin = shutil.which("emulator")
        if not emulator_bin:
            return f"Error: Emulator binary not found at {os.path.join(sdk_root, 'emulator')}."

    try:
        # Check if AVD exists
        list_cmd = [emulator_bin, "-list-avds"]
        result = subprocess.run(list_cmd, capture_output=True, text=True)
        available_avds = result.stdout.strip().split('\n')
        # Cleanup output (remove empty lines/logs)
        available_avds = [a.strip() for a in available_avds if a.strip()]

        if avd_name not in available_avds:
            return f"Error: AVD '{avd_name}' not found. Available: {available_avds}"

        # Launch detached
        cmd = [emulator_bin, "@" + avd_name]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Success: Command sent to launch '{avd_name}' on {platform.system()}."

    except Exception as e:
        return f"Critical Error starting emulator: {str(e)}"


@mcp.tool()
def start_appium_server(port: int = 4723):
    """
    Starts the Appium Server (Cross-Platform).
    """
    # 1. Check if running
    try:
        response = requests.get(f"http://127.0.0.1:{port}/status", timeout=1)
        if response.status_code == 200:
            return f"Appium is already running on port {port}."
    except:
        pass

    # 2. Find executable (appium.cmd on Windows, appium on Mac/Linux)
    appium_executable = shutil.which("appium")

    # Windows specific fallback if not in PATH
    if not appium_executable and platform.system() == "Windows":
        # Check standard npm locations
        possible_path = os.path.join(os.environ.get("APPDATA"), "npm", "appium.cmd")
        if os.path.exists(possible_path):
            appium_executable = possible_path

    if not appium_executable:
        return "Error: 'appium' command not found. Install nodejs and run 'npm install -g appium'."

    # 3. Start server
    log_file_path = os.path.join(os.getcwd(), "appium_server.log")
    try:
        with open(log_file_path, "w") as log_file:
            # On Windows, shell=True is sometimes needed for .cmd files if not direct executable
            use_shell = True if platform.system() == "Windows" else False

            subprocess.Popen(
                [appium_executable, "-p", str(port), "--allow-cors"],
                stdout=log_file,
                stderr=log_file,
                shell=use_shell
            )
        time.sleep(3)
        return f"Appium Server started on {platform.system()} (Port {port}). Logs: {log_file_path}"
    except Exception as e:
        return f"Failed to start Appium: {str(e)}"


@mcp.tool()
def scaffold_bdd_framework(project_name: str):
    """
    Creates BDD project structure using OS-agnostic paths.
    """
    cwd = os.getcwd()
    base_path = os.path.join(cwd, project_name)

    # OS-agnostic path joining
    dirs = [
        os.path.join(base_path, "src", "test", "java", "stepDefinitions"),
        os.path.join(base_path, "src", "test", "java", "runners"),
        os.path.join(base_path, "src", "test", "java", "pages"),
        os.path.join(base_path, "src", "test", "resources", "features"),
        os.path.join(base_path, "src", "main", "resources")
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)

    # Simple POM creation
    pom_path = os.path.join(base_path, "pom.xml")
    if not os.path.exists(pom_path):
        with open(pom_path, "w") as f:
            f.write(
                f"<project><modelVersion>4.0.0</modelVersion><groupId>com.example</groupId><artifactId>{project_name}</artifactId><version>1.0</version></project>")

    return f"Framework scaffolded at {base_path}"


@mcp.tool()
def launch_app_and_inspector(platform_name: str, app_filename: str, device_name: str):
    """
    Launch App. Supports generic filename search in local 'apps' folder.
    """
    global driver

    # Smart Path Logic
    app_path = app_filename
    if not os.path.exists(app_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fallback_path = os.path.join(base_dir, "apps", os.path.basename(app_filename))
        if os.path.exists(fallback_path):
            app_path = fallback_path
        else:
            return f"Error: App '{app_filename}' not found locally or in {os.path.join(base_dir, 'apps')}"

    try:
        options = None
        if platform_name.lower() == 'android':
            options = UiAutomator2Options()
            options.automation_name = 'UiAutomator2'
        elif platform_name.lower() == 'ios':
            if platform.system() == "Windows":
                return "Error: iOS automation is not supported on Windows."
            options = XCUITestOptions()
            options.automation_name = 'XCUITest'

        if options:
            options.platform_name = platform_name
            options.device_name = device_name
            options.app = app_path
            options.no_reset = False

        driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
        return f"Success: Launched {os.path.basename(app_path)}"
    except Exception as e:
        return f"Launch Failed: {str(e)}"


# Extract Locators tool remains mostly the same, just ensure imports are there
@mcp.tool()
def extract_page_locators(page_name: str, save_path: str):
    global driver
    if not driver:
        return "Error: No active driver."
    try:
        source = driver.page_source
        root = ET.fromstring(source)
        locators = []
        for element in root.iter():
            res_id = element.attrib.get('resource-id')
            content_desc = element.attrib.get('content-desc')
            if res_id:
                # Format locator logic here
                locators.append(f'// ID: {res_id}')
            elif content_desc:
                locators.append(f'// AccessID: {content_desc}')

        # Ensure directory exists
        os.makedirs(save_path, exist_ok=True)
        full_path = os.path.join(save_path, f"{page_name}.java")
        with open(full_path, "w") as f:
            f.write(f"public class {page_name} {{\n" + "\n".join(locators) + "\n}")
        return f"Saved to {full_path}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()