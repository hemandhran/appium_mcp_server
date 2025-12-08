from mcp.server.fastmcp import FastMCP
import subprocess
import os
import time
import shutil
import requests  # Ensure you run: pip install requests
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from selenium.webdriver.common.by import By
import xml.etree.ElementTree as ET

# Initialize the MCP Server
mcp = FastMCP("LocalAppiumAutomationHelper")

# Global driver to hold the session active between tools
driver = None


@mcp.tool()
def start_appium_server(port: int = 4723):
    """
    Starts the Appium server on a specified port.
    """
    try:
        # Command to start Appium
        cmd = ["appium", "-p", str(port)]
        
        # Start Appium in a detached process
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Give it a moment to start
        time.sleep(5)
        
        return f"Appium server started on port {port}. Please wait a few seconds for it to initialize."
    except FileNotFoundError:
        return "Error: 'appium' command not found. Make sure Appium is installed and in your PATH."
    except Exception as e:
        return f"Error starting Appium server: {str(e)}"


@mcp.tool()
def start_android_emulator(avd_name: str):
    """
    Starts a local Android Emulator using the given AVD name.
    """
    # 1. Define the absolute path to the emulator executable for macOS
    # This is the standard path for Mac. If yours is different, update it.
    user_home = os.path.expanduser("~")
    emulator_path = os.path.join(user_home, "Library", "Android", "sdk", "emulator", "emulator")

    if not os.path.exists(emulator_path):
        return f"Error: Emulator binary not found at {emulator_path}. Please check your Android SDK installation."

    try:
        # 2. Command to list AVDs to verify the name first
        # We check if the requested AVD actually exists to avoid silent failures
        list_cmd = [emulator_path, "-list-avds"]
        result = subprocess.run(list_cmd, capture_output=True, text=True)
        available_avds = result.stdout.strip().split('\n')

        if avd_name not in available_avds:
            return f"Error: AVD '{avd_name}' not found. Available AVDs: {available_avds}"

        # 3. Launch emulator detached
        # We intentionally do NOT pipe stdout/stderr to DEVNULL so we can see issues if needed,
        # but usually, we just want to fire and forget.
        cmd = [emulator_path, "@" + avd_name]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return f"Success: Command sent to launch '{avd_name}' from {emulator_path}. Please wait ~30s."

    except Exception as e:
        return f"Critical Error starting emulator: {str(e)}"


@mcp.tool()
def scaffold_bdd_framework(project_name: str, location: str):
    """
    Creates a folder structure for a Java/Cucumber/Appium BDD project.
    Creates: src/test/java, src/test/resources/features, pageObjects, etc.
    """
    base_path = os.path.join(location, project_name)

    dirs = [
        f"{base_path}/src/test/java/stepDefinitions",
        f"{base_path}/src/test/java/runners",
        f"{base_path}/src/test/java/pages",
        f"{base_path}/src/test/resources/features",
        f"{base_path}/src/main/resources"
    ]

    created_log = []
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        created_log.append(d)

    # Create a dummy pom.xml (Maven) or build.gradle
    pom_path = os.path.join(base_path, "pom.xml")
    with open(pom_path, "w") as f:
        f.write("<project> ... (Basic Maven Template with Appium/Cucumber dependencies) ... </project>")

    return f"Framework scaffolded successfully at {base_path}. Created directories: {created_log}"


@mcp.tool()
def launch_app_and_inspector(platform: str, app_path: str, device_name: str):
    """
    Launches the Appium driver.
    Smart Feature: If app_path is not found, it checks the MCP server's local 'apps' folder.
    """
    global driver

    # --- SMART PATH LOGIC START ---
    # 1. If the path provided doesn't exist, check the server's own 'apps' folder
    if not os.path.exists(app_path):
        # Get the folder where THIS python script lives
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct path: .../Appium_MCP/apps/Android.Sauce...
        fallback_path = os.path.join(base_dir, "apps", os.path.basename(app_path))

        if os.path.exists(fallback_path):
            print(f"Found app in server directory: {fallback_path}")
            app_path = fallback_path
        else:
            return f"Error: Could not find app at '{app_path}' or '{fallback_path}'"
    # --- SMART PATH LOGIC END ---

    try:
        if platform.lower() == 'android':
            options = UiAutomator2Options()
            options.platform_name = 'Android'
            options.device_name = device_name
            options.app = app_path
            options.automation_name = 'UiAutomator2'
            # Important: Don't reset app state if you want to speed up tests
            options.no_reset = False
        elif platform.lower() == 'ios':
            options = XCUITestOptions()
            options.platform_name = 'iOS'
            options.device_name = device_name
            options.app = app_path
            options.automation_name = 'XCUITest'
        else:
            return "Invalid platform. Use Android or iOS."

        # Connect to local Appium server
        driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
        return f"Success: Launched {os.path.basename(app_path)}. Session is active."
    except Exception as e:
        return f"Failed to launch app: {str(e)}"


@mcp.tool()
def extract_page_locators(page_name: str, save_path: str):
    """
    Scrapes the current screen of the active Appium session.
    Finds all elements with IDs or Accessibility IDs and saves them to a Page Object file.
    """
    global driver
    if not driver:
        return "Error: No active driver. Run 'launch_app_and_inspector' first."

    try:
        # Get the page source (XML)
        source = driver.page_source
        root = ET.fromstring(source)

        locators = []

        # Parse XML to find useful attributes
        # This checks for resource-id (Android) or name/accessibility-id (iOS)
        for element in root.iter():
            res_id = element.attrib.get('resource-id')
            content_desc = element.attrib.get('content-desc')
            name = element.attrib.get('name')

            if res_id:
                locators.append(
                    f'    @AndroidFindBy(id = "{res_id}")\n    private MobileElement {res_id.split("/")[-1]};')
            elif content_desc:
                locators.append(
                    f'    @AndroidFindBy(accessibility = "{content_desc}")\n    private MobileElement {content_desc.replace(" ", "_")};')
            elif name:
                locators.append(
                    f'    @iOSXCUITFindBy(accessibility = "{name}")\n    private MobileElement {name.replace(" ", "_")};')

        # Write to a Java Page Object file
        file_content = f"public class {page_name} {{\n" + "\n".join(locators) + "\n}"
        full_path = os.path.join(save_path, f"{page_name}.java")

        with open(full_path, "w") as f:
            f.write(file_content)

        return f"Locators extracted and saved to {full_path}"

    except Exception as e:
        return f"Error extracting locators: {str(e)}"


@mcp.tool()
def start_appium_server(port: int = 4723):
    """
    Starts the Appium Server in the background.
    Logs are saved to 'appium_server.log' in the current directory.
    """
    # 1. Check if Appium is already running
    try:
        response = requests.get(f"http://127.0.0.1:{port}/status", timeout=1)
        if response.status_code == 200:
            return f"Appium is already running on port {port}. No action needed."
    except:
        pass  # Not running, proceed to start

    # 2. Find the Appium executable path
    appium_executable = shutil.which("appium")
    if not appium_executable:
        # Fallback for common Mac path if 'which' fails
        if os.path.exists("/usr/local/bin/appium"):
            appium_executable = "/usr/local/bin/appium"
        elif os.path.exists("/opt/homebrew/bin/appium"):
            appium_executable = "/opt/homebrew/bin/appium"
        else:
            return "Error: Could not find 'appium'. Please install it via 'npm install -g appium'."

    # 3. Start the server and redirect logs
    log_file_path = os.path.join(os.getcwd(), "appium_server.log")
    try:
        # Open the log file in write mode
        with open(log_file_path, "w") as log_file:
            # Popen starts the process without blocking the script
            subprocess.Popen(
                [appium_executable, "-p", str(port), "--allow-cors"],
                stdout=log_file,
                stderr=log_file
            )

        # Give it a moment to spin up
        time.sleep(3)
        return f"Appium Server started successfully on port {port}. Logs: {log_file_path}"

    except Exception as e:
        return f"Failed to start Appium Server: {str(e)}"


if __name__ == "__main__":
    # This starts the server on stdio (standard input/output) for the IDE to talk to
    mcp.run()