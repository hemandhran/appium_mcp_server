from mcp.server.fastmcp import FastMCP
import subprocess
import os
import time
import shutil
import platform
import json
import requests
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
import xml.etree.ElementTree as ET

# Initialize the MCP Server
mcp = FastMCP("UniversalAppiumHelper")

# Global driver
driver = None


# --- UTILITIES ---
def is_mac():
    return platform.system() == "Darwin"


def get_android_sdk_root():
    if os.environ.get("ANDROID_HOME"): return os.environ.get("ANDROID_HOME")
    if os.environ.get("ANDROID_SDK_ROOT"): return os.environ.get("ANDROID_SDK_ROOT")
    user_home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
    elif is_mac():
        return os.path.join(user_home, "Library", "Android", "sdk")
    return None


# --- ANDROID TOOLS (Kept from previous version) ---
@mcp.tool()
def list_android_avds():
    """Lists available Android Virtual Devices (AVDs)."""
    sdk_root = get_android_sdk_root()
    if not sdk_root:
        return "Error: Android SDK not found."

    emulator_bin = os.path.join(sdk_root, "emulator", "emulator")
    if platform.system() == "Windows":
        emulator_bin += ".exe"

    if not os.path.exists(emulator_bin):
        emulator_bin = shutil.which("emulator")
        if not emulator_bin:
            return "Error: Emulator binary not found."

    try:
        cmd = [emulator_bin, "-list-avds"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        avds = result.stdout.strip().split('\n')
        return "Available AVDs:\n" + "\n".join(avds)
    except Exception as e:
        return f"Error listing AVDs: {str(e)}"


@mcp.tool()
def start_android_emulator(avd_name: str):
    """Starts a local Android Emulator."""
    sdk_root = get_android_sdk_root()
    if not sdk_root: return "Error: Android SDK not found."

    emulator_bin = os.path.join(sdk_root, "emulator", "emulator")
    if platform.system() == "Windows": emulator_bin += ".exe"

    if not os.path.exists(emulator_bin):
        emulator_bin = shutil.which("emulator")
        if not emulator_bin: return "Error: Emulator binary not found."

    try:
        cmd = [emulator_bin, "@" + avd_name]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Success: Command sent to launch Android AVD '{avd_name}'."
    except Exception as e:
        return f"Error starting emulator: {str(e)}"


# --- NEW iOS TOOLS ---

@mcp.tool()
def list_ios_simulators():
    """
    (Mac Only) Lists all available iOS Simulators installed via Xcode.
    Returns the Name and UUID of devices.
    """
    if not is_mac(): return "Error: iOS Simulators are only available on macOS."

    try:
        # Get JSON list of devices
        cmd = ["xcrun", "simctl", "list", "devices", "available", "-j"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        simulators = []
        # Parse the JSON structure { "runtimes": { "iOS 17.0": [ ... ] } }
        for runtime, devices in data.get("devices", {}).items():
            if "iOS" in runtime or "iPhone" in runtime:  # Filter for iOS devices
                for device in devices:
                    if device.get("isAvailable"):
                        simulators.append(f"{device['name']} ({device['udid']}) - {device['state']}")

        return "Available iOS Simulators:\n" + "\n".join(simulators)
    except Exception as e:
        return f"Failed to list simulators: {str(e)}"


@mcp.tool()
def start_ios_simulator(device_name_or_uuid: str):
    """
    (Mac Only) Boots an iOS Simulator and opens the Simulator App.
    Accepts exact Name (e.g., "iPhone 15") or UUID.
    """
    if not is_mac(): return "Error: iOS Simulators are only available on macOS."

    try:
        # 1. Boot the device
        # Note: 'boot' might fail if already booted, so we ignore stderr usually,
        # but let's check for "Unable to boot" errors specifically if needed.
        subprocess.run(["xcrun", "simctl", "boot", device_name_or_uuid], check=False)

        # 2. Open the Simulator GUI application
        subprocess.run(["open", "-a", "Simulator"], check=True)

        return f"Success: Boot command sent for '{device_name_or_uuid}' and Simulator app opened."
    except Exception as e:
        return f"Error booting simulator: {str(e)}"


@mcp.tool()
def build_and_install_ios_app(project_path: str, scheme: str, device_name_or_uuid: str):
    """
    (Mac Only) Builds an Xcode Project (.xcodeproj or .xcworkspace) and installs the .app to a simulator.

    Args:
        project_path: Full path to the folder containing .xcodeproj or .xcworkspace
        scheme: The build scheme name (e.g., "MyApp" or "MyApp-Debug")
        device_name_or_uuid: The Simulator to install on (must be booted)
    """
    if not is_mac(): return "Error: Xcode build requires macOS."

    # 1. Construct Build Command
    # We build into a temporary "derivedData" folder to easily find the .app later
    derived_data = os.path.join(project_path, "build_mcp")

    cmd = [
        "xcodebuild",
        "-scheme", scheme,
        "-sdk", "iphonesimulator",
        "-configuration", "Debug",
        "-derivedDataPath", derived_data
    ]

    # Check if workspace or project
    if os.path.exists(os.path.join(project_path, f"{scheme}.xcworkspace")):
        cmd.extend(["-workspace", os.path.join(project_path, f"{scheme}.xcworkspace")])
    else:
        # Attempt to find project file
        files = [f for f in os.listdir(project_path) if f.endswith(".xcodeproj")]
        if not files: return "Error: No .xcodeproj found in path."
        cmd.extend(["-project", os.path.join(project_path, files[0])])

    try:
        # 2. Run Build (This can take time)
        print("Starting Xcode Build... this may take a minute.")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        # 3. Find the resulting .app file
        # Usually in: .../Build/Products/Debug-iphonesimulator/AppName.app
        products_dir = os.path.join(derived_data, "Build", "Products", "Debug-iphonesimulator")
        if not os.path.exists(products_dir):
            return f"Build failed: Output directory {products_dir} not found."

        app_files = [f for f in os.listdir(products_dir) if f.endswith(".app")]
        if not app_files:
            return "Build successful, but could not locate .app file to install."

        app_path = os.path.join(products_dir, app_files[0])

        # 4. Install to Simulator
        install_cmd = ["xcrun", "simctl", "install", device_name_or_uuid, app_path]
        subprocess.run(install_cmd, check=True)

        return f"Success: Built '{app_files[0]}' and installed on {device_name_or_uuid}."

    except subprocess.CalledProcessError as e:
        return f"Error during build/install: {e.stderr.decode('utf-8') if e.stderr else str(e)}"
    except Exception as e:
        return f"Critical error: {str(e)}"


# --- SHARED TOOLS ---
@mcp.tool()
def start_appium_server(port: int = 4723):
    """Starts Appium Server (Cross-Platform)."""
    # (Same logic as before, just kept concise for this snippet)
    try:
        requests.get(f"http://127.0.0.1:{port}/status", timeout=1)
        return f"Appium running on {port}."
    except:
        pass

    appium_exec = shutil.which("appium")
    if not appium_exec and platform.system() == "Windows":
        # Check common Windows path
        appium_exec = os.path.join(os.environ.get("APPDATA", ""), "npm", "appium.cmd")

    if not appium_exec: return "Error: 'appium' command not found."

    log_file = os.path.join(os.getcwd(), "appium_server.log")
    with open(log_file, "w") as f:
        use_shell = True if platform.system() == "Windows" else False
        subprocess.Popen([appium_exec, "-p", str(port), "--allow-cors"], stdout=f, stderr=f, shell=use_shell)
    time.sleep(3)
    return f"Appium started on port {port}."


@mcp.tool()
def scaffold_bdd_framework(project_name: str):
    """Creates BDD folder structure."""
    # (Same logic as before)
    base = os.path.join(os.getcwd(), project_name)
    dirs = ["src/test/java/stepDefinitions", "src/test/java/pages", "src/test/resources/features"]
    for d in dirs: os.makedirs(os.path.join(base, d), exist_ok=True)
    return f"Scaffolded {project_name}"


@mcp.tool()
@mcp.tool()
def launch_app_and_inspector(platform_name: str, app_filename: str, device_name: str):
    """
    Installs and Launches an mobile app on a device/simulator.
    Use this tool to 'install', 'open', or 'run' an APK or APP file.
    Smart Feature: If app_filename is not found, it automatically checks the MCP server's local 'apps' folder.
    """
    global driver

    # Path Logic
    app_path = app_filename
    if not os.path.exists(app_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fallback = os.path.join(base_dir, "apps", os.path.basename(app_filename))
        if os.path.exists(fallback):
            app_path = fallback
        # On iOS, we often just launch by Bundle ID if app is already installed
        elif platform_name.lower() == 'ios' and '.' in app_filename and '/' not in app_filename:
            app_path = app_filename  # Treat as Bundle ID (e.g., com.apple.settings)
        else:
            return f"Error: App {app_filename} not found."

    try:
        options = None
        if platform_name.lower() == 'android':
            options = UiAutomator2Options()
            options.automation_name = 'UiAutomator2'
        elif platform_name.lower() == 'ios':
            if not is_mac(): return "iOS automation requires macOS."
            options = XCUITestOptions()
            options.automation_name = 'XCUITest'
            # iOS Specifics
            options.wda_launch_timeout = 60000  # Wait for WebDriverAgent

        if options:
            options.platform_name = platform_name
            options.device_name = device_name
            # If app_path is a file, use 'app'; if it looks like a Bundle ID, use 'bundleId'
            if os.path.exists(app_path):
                options.app = app_path
            else:
                options.bundle_id = app_path

        driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
        return f"Success: Launched {app_filename} on {platform_name}."
    except Exception as e:
        return f"Launch Failed: {str(e)}"


@mcp.tool()
def extract_page_locators(page_name: str, save_path: str):
    """Extracts locators from active driver session."""
    global driver
    if not driver: return "Error: No active driver."
    try:
        source = driver.page_source
        root = ET.fromstring(source)
        locators = []
        for element in root.iter():
            # Android
            res_id = element.attrib.get('resource-id')
            # iOS
            name = element.attrib.get('name')
            label = element.attrib.get('label')

            if res_id:
                locators.append(f'    @AndroidFindBy(id="{res_id}")')
                locators.append(f'    public MobileElement {res_id.split("/")[-1]};')
            elif name:
                safe_name = "".join(x for x in name if x.isalnum())
                if safe_name:
                    locators.append(f'    @iOSXCUITFindBy(accessibility="{name}")')
                    locators.append(f'    public MobileElement {safe_name};')

        file_content = f"public class {page_name} {{\n" + "\n".join(locators) + "\n}"
        full_path = os.path.join(save_path, f"{page_name}.java")
        with open(full_path, "w") as f:
            f.write(file_content)
        return f"Saved to {full_path}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()