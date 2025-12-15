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
import difflib

# Initialize the MCP Server
mcp = FastMCP("UniversalAppiumHelper")

# Global driver
driver = None


# --- UTILITIES ---
def is_mac():
    """
    Checks if the current operating system is macOS.

    Returns:
        bool: True if the OS is macOS (Darwin), False otherwise.
    """
    return platform.system() == "Darwin"


def get_android_sdk_root():
    """
    Finds the root directory of the Android SDK.

    It checks for ANDROID_HOME and ANDROID_SDK_ROOT environment variables first.
    If they are not found, it falls back to default installation paths for Windows and macOS.

    Returns:
        str or None: The absolute path to the Android SDK root, or None if not found.
    """
    if os.environ.get("ANDROID_HOME"): return os.environ.get("ANDROID_HOME")
    if os.environ.get("ANDROID_SDK_ROOT"): return os.environ.get("ANDROID_SDK_ROOT")
    user_home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
    elif is_mac():
        return os.path.join(user_home, "Library", "Android", "sdk")
    return None

def get_avdmanager_path(sdk_root):
    """Finds the avdmanager binary in the SDK."""
    if not sdk_root: return None
    
    # Check cmdline-tools/latest/bin (Standard for newer SDKs)
    path = os.path.join(sdk_root, "cmdline-tools", "latest", "bin", "avdmanager")
    if platform.system() == "Windows": path += ".bat"
    if os.path.exists(path): return path
    
    # Check cmdline-tools/bin (Older structure)
    path = os.path.join(sdk_root, "cmdline-tools", "bin", "avdmanager")
    if platform.system() == "Windows": path += ".bat"
    if os.path.exists(path): return path

    # Check tools/bin (Legacy)
    path = os.path.join(sdk_root, "tools", "bin", "avdmanager")
    if platform.system() == "Windows": path += ".bat"
    if os.path.exists(path): return path
    
    return shutil.which("avdmanager")


# --- ANDROID TOOLS ---
@mcp.tool()
def list_android_avds():
    """
    Lists all available Android Virtual Devices (AVDs) that can be started.

    This tool uses the `emulator -list-avds` command.

    Returns:
        str: A formatted string listing the names of available AVDs, or an error message.
    """
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
def list_connected_android_devices():
    """
    Lists all physically connected Android devices and running emulators.

    This tool uses the `adb devices` command.

    Returns:
        str: A formatted string listing the UDIDs of connected devices, or an error message.
    """
    sdk_root = get_android_sdk_root()
    if not sdk_root:
        return "Error: Android SDK not found."

    adb_bin = os.path.join(sdk_root, "platform-tools", "adb")
    if platform.system() == "Windows":
        adb_bin += ".exe"

    if not os.path.exists(adb_bin):
        adb_bin = shutil.which("adb")
        if not adb_bin:
            return "Error: ADB binary not found."

    try:
        cmd = [adb_bin, "devices"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        devices = result.stdout.strip().split('\n')[1:]  # Skip the "List of devices attached" header
        connected_devices = [line.split('\t')[0] for line in devices if line]
        return "Connected Android Devices:\n" + "\n".join(connected_devices)
    except Exception as e:
        return f"Error listing connected Android devices: {str(e)}"


@mcp.tool()
def create_android_avd(name: str, package: str, device: str = "pixel"):
    """
    Creates a new Android Virtual Device (AVD) using avdmanager.

    Args:
        name (str): The name for the new AVD (e.g., "My_Pixel_9").
        package (str): The SDK package path (e.g., "system-images;android-34;google_apis;x86_64").
                       Note: This package must already be installed via sdkmanager.
        device (str, optional): The device definition to use (e.g., "pixel", "pixel_6", "Nexus 5"). Defaults to "pixel".

    Returns:
        str: Success or error message.
    """
    sdk_root = get_android_sdk_root()
    if not sdk_root: return "Error: Android SDK not found."
    
    avdmanager = get_avdmanager_path(sdk_root)
    if not avdmanager: return "Error: avdmanager binary not found in Android SDK."

    # Command: avdmanager create avd -n <name> -k <package> -d <device>
    cmd = [avdmanager, "create", "avd", "-n", name, "-k", package, "-d", device]
    
    try:
        # We pipe "no" to stdin because avdmanager asks "Do you wish to create a custom hardware profile? [no]"
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(input="no\n")
        
        if process.returncode == 0:
            return f"Success: Created AVD '{name}' using package '{package}' and device '{device}'."
        else:
            return f"Error creating AVD:\nSTDOUT: {stdout}\nSTDERR: {stderr}"
    except Exception as e:
        return f"Exception during AVD creation: {str(e)}"


@mcp.tool()
def start_android_emulator(avd_name: str):
    """
    Starts a local Android emulator (AVD).

    Args:
        avd_name (str): The name of the Android Virtual Device to start.

    Returns:
        str: A success or error message.
    """
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


# --- iOS TOOLS ---

@mcp.tool()
def list_ios_simulators():
    """
    (Mac Only) Lists all available iOS Simulators installed via Xcode.

    This tool uses the `xcrun simctl list` command.

    Returns:
        str: A formatted string listing available simulators with their name, UDID, and state, or an error message.
    """
    if not is_mac(): return "Error: iOS Simulators are only available on macOS."

    try:
        cmd = ["xcrun", "simctl", "list", "devices", "available", "-j"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        simulators = []
        for runtime, devices in data.get("devices", {}).items():
            if "iOS" in runtime or "iPhone" in runtime:
                for device in devices:
                    if device.get("isAvailable"):
                        simulators.append(f"{device['name']} ({device['udid']}) - {device['state']}")

        return "Available iOS Simulators:\n" + "\n".join(simulators)
    except Exception as e:
        return f"Failed to list simulators: {str(e)}"


@mcp.tool()
def list_connected_ios_devices():
    """
    (Mac Only) Lists all physically connected iOS devices.

    This tool uses the `xcrun xctrace list devices` command.

    Returns:
        str: A formatted string listing connected iOS devices, or an error message.
    """
    if not is_mac():
        return "Error: iOS devices can only be listed on macOS."

    try:
        cmd = ["xcrun", "xctrace", "list", "devices"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout
        devices = []
        for line in output.splitlines():
            if "iPhone" in line and "Simulator" not in line:
                devices.append(line)
        return "Connected iOS Devices:\n" + "\n".join(devices)
    except Exception as e:
        return f"Error listing connected iOS devices: {str(e)}"


@mcp.tool()
def start_ios_simulator(device_name_or_uuid: str):
    """
    (Mac Only) Boots an iOS Simulator and opens the Simulator application.

    Args:
        device_name_or_uuid (str): The name (e.g., "iPhone 15") or UUID of the simulator to boot.

    Returns:
        str: A success or error message.
    """
    if not is_mac(): return "Error: iOS Simulators are only available on macOS."

    try:
        subprocess.run(["xcrun", "simctl", "boot", device_name_or_uuid], check=False)
        subprocess.run(["open", "-a", "Simulator"], check=True)
        return f"Success: Boot command sent for '{device_name_or_uuid}' and Simulator app opened."
    except Exception as e:
        return f"Error booting simulator: {str(e)}"


@mcp.tool()
def build_and_install_ios_app(project_path: str, scheme: str, device_name_or_uuid: str):
    """
    (Mac Only) Builds an Xcode project and installs the app to a running simulator.

    Args:
        project_path (str): The full path to the folder containing the .xcodeproj or .xcworkspace file.
        scheme (str): The Xcode build scheme name (e.g., "MyApp-Debug").
        device_name_or_uuid (str): The UUID of the booted simulator to install the app on.

    Returns:
        str: A success or error message.
    """
    if not is_mac(): return "Error: Xcode build requires macOS."

    derived_data = os.path.join(project_path, "build_mcp")
    cmd = [
        "xcodebuild", "-scheme", scheme, "-sdk", "iphonesimulator",
        "-configuration", "Debug", "-derivedDataPath", derived_data
    ]

    if os.path.exists(os.path.join(project_path, f"{scheme}.xcworkspace")):
        cmd.extend(["-workspace", os.path.join(project_path, f"{scheme}.xcworkspace")])
    else:
        files = [f for f in os.listdir(project_path) if f.endswith(".xcodeproj")]
        if not files: return "Error: No .xcodeproj found in path."
        cmd.extend(["-project", os.path.join(project_path, files[0])])

    try:
        print("Starting Xcode Build... this may take a minute.")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        products_dir = os.path.join(derived_data, "Build", "Products", "Debug-iphonesimulator")
        if not os.path.exists(products_dir):
            return f"Build failed: Output directory {products_dir} not found."

        app_files = [f for f in os.listdir(products_dir) if f.endswith(".app")]
        if not app_files:
            return "Build successful, but could not locate .app file to install."

        app_path = os.path.join(products_dir, app_files[0])
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
    """
    Starts the Appium server on a specified port if it's not already running.

    Args:
        port (int, optional): The port number to start Appium on. Defaults to 4723.

    Returns:
        str: A message indicating the status of the Appium server.
    """
    try:
        requests.get(f"http://127.0.0.1:{port}/status", timeout=1)
        return f"Appium is already running on port {port}."
    except:
        pass

    appium_exec = shutil.which("appium")
    if not appium_exec and platform.system() == "Windows":
        appium_exec = os.path.join(os.environ.get("APPDATA", ""), "npm", "appium.cmd")

    if not appium_exec: return "Error: 'appium' command not found in system PATH."

    log_file = os.path.join(os.getcwd(), "appium_server.log")
    with open(log_file, "w") as f:
        use_shell = True if platform.system() == "Windows" else False
        subprocess.Popen([appium_exec, "-p", str(port), "--allow-cors"], stdout=f, stderr=f, shell=use_shell)
    time.sleep(3)
    return f"Appium server started on port {port}. Log file at: {log_file}"


@mcp.tool()
def scaffold_bdd_framework(project_name: str):
    """
    Creates a standard BDD (Behavior-Driven Development) folder structure.

    Args:
        project_name (str): The name of the root folder for the new project.

    Returns:
        str: A success message indicating the project was scaffolded.
    """
    base = os.path.join(os.getcwd(), project_name)
    dirs = ["src/test/java/stepDefinitions", "src/test/java/pages", "src/test/resources/features"]
    for d in dirs: os.makedirs(os.path.join(base, d), exist_ok=True)
    return f"BDD framework scaffolded at: {base}"


@mcp.tool()
def launch_app_and_inspector(platform_name: str, app_filename: str, device_name: str):
    """
    Installs and launches a mobile app on a specified device or simulator.

    This function initializes the global Appium driver, which is required for other tools
    like `extract_page_locators`.

    Args:
        platform_name (str): The mobile platform, either 'Android' or 'iOS'.
        app_filename (str): The path to the .apk or .app file, or the bundle ID for an installed iOS app.
        device_name (str): The name of the device or simulator (e.g., "Pixel_6_Pro", "iPhone 15").

    Returns:
        str: A success or error message.
    """
    global driver

    app_path = app_filename
    if not os.path.exists(app_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fallback = os.path.join(base_dir, "apps", os.path.basename(app_filename))
        if os.path.exists(fallback):
            app_path = fallback
        elif platform_name.lower() == 'ios' and '.' in app_filename and '/' not in app_filename:
            app_path = app_filename
        else:
            return f"Error: App file or bundle ID '{app_filename}' not found."

    try:
        options = None
        if platform_name.lower() == 'android':
            options = UiAutomator2Options()
            options.automation_name = 'UiAutomator2'
            options.app_wait_activity = '*'
            options.app_wait_duration = 30000
        elif platform_name.lower() == 'ios':
            if not is_mac(): return "iOS automation requires macOS."
            options = XCUITestOptions()
            options.automation_name = 'XCUITest'
            options.wda_launch_timeout = 60000

        if options:
            options.platform_name = platform_name
            options.device_name = device_name
            if os.path.exists(app_path):
                options.app = app_path
            else:
                options.bundle_id = app_path

        driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
        return f"Success: Launched '{app_filename}' on {platform_name} device '{device_name}'."
    except Exception as e:
        return f"Launch Failed: {str(e)}"


@mcp.tool()
def extract_page_locators(page_name: str, save_path: str):
    """
    Extracts UI element locators from the current screen and generates a Java Page Object class.

    Requires an active Appium driver session, initiated by `launch_app_and_inspector`.

    Args:
        page_name (str): The desired class name for the generated Java file (e.g., "LoginPage").
        save_path (str): The directory path where the Java file should be saved.

    Returns:
        str: A success message with the path to the saved file, or an error message.
    """
    global driver
    if not driver: return "Error: No active Appium driver session found. Use 'launch_app_and_inspector' first."
    try:
        source = driver.page_source
        root = ET.fromstring(source)
        locators = []
        for element in root.iter():
            res_id = element.attrib.get('resource-id')
            name = element.attrib.get('name')

            if res_id:
                locators.append(f'    @AndroidFindBy(id="{res_id}")')
                locators.append(f'    public MobileElement {res_id.split("/")[-1]};')
            elif name:
                safe_name = "".join(x for x in name if x.isalnum())
                if safe_name:
                    locators.append(f'    @iOSXCUITFindBy(accessibilityId="{name}")')
                    locators.append(f'    public MobileElement {safe_name};')

        file_content = f"public class {page_name} {{\n\n" + "\n\n".join(locators) + "\n\n}"
        full_path = os.path.join(save_path, f"{page_name}.java")
        with open(full_path, "w") as f:
            f.write(file_content)
        return f"Page Object class saved to: {full_path}"
    except Exception as e:
        return f"Error extracting locators: {str(e)}"


@mcp.tool()
def heal_locator(target_text: str, expected_type: str = None):
    """
    Finds a reliable locator for an element based on its visible text.

    This is useful for self-healing when a locator has changed. It scans the current
    screen for an element with matching text and returns its current, valid locator.

    Args:
        target_text (str): The visible text (or content-desc) of the element to find.
        expected_type (str, optional): The expected class name of the element (e.g., "android.widget.Button").

    Returns:
        str: A string with the best locator found (e.g., "id: new_id"), or an error message.
    """
    global driver
    if not driver:
        return "Error: No active Appium driver session found. Use 'launch_app_and_inspector' first."

    try:
        source = driver.page_source
        root = ET.fromstring(source)
        candidates = []

        for element in root.iter():
            # Get all relevant text attributes
            text = element.attrib.get('text', '')
            content_desc = element.attrib.get('content-desc', '')
            res_id = element.attrib.get('resource-id', '')
            name = element.attrib.get('name', '') # For iOS
            label = element.attrib.get('label', '') # For iOS
            elem_type = element.tag

            # Check if the element text is a close match
            current_text = text or content_desc or name or label
            if not current_text:
                continue

            # Check type if specified
            if expected_type and elem_type != expected_type:
                continue

            # Score based on similarity
            similarity = difflib.SequenceMatcher(None, target_text, current_text).ratio()
            if similarity > 0.8: # High confidence threshold
                # Prefer ID or accessibility ID if available
                if res_id:
                    candidates.append((similarity, f"id: {res_id}"))
                elif name:
                     candidates.append((similarity, f"accessibilityId: {name}"))
                else: # Fallback to XPath
                    # Simple XPath based on text
                    xpath = f"//[{elem_type} and @text='{current_text}']"
                    candidates.append((similarity, f"xpath: {xpath}"))

        if not candidates:
            return "Could not find a suitable element to heal the locator."

        # Return the best candidate
        candidates.sort(key=lambda x: x[0], reverse=True)
        return f"Found best match: {candidates[0][1]}"

    except Exception as e:
        return f"Error during locator healing: {str(e)}"


@mcp.tool()
def run_parallel_tests(device_names: str, platform_name: str, test_command_pattern: str):
    """
    Starts multiple devices and executes a test command on each in parallel.

    Args:
        device_names (str): Comma-separated list of AVD names (Android) or Simulator names (iOS).
        platform_name (str): 'Android' or 'iOS'.
        test_command_pattern (str): Command to run. Use '{udid}' as placeholder for Device ID.
                                    Example: "mvn test -Dudid={udid} -DplatformName=Android"

    Returns:
        str: A report of the execution status for each device.
    """
    device_list = [d.strip() for d in device_names.split(',') if d.strip()]
    if not device_list:
        return "Error: No devices specified."

    started_udids = []
    
    if platform_name.lower() == 'android':
        # 1. Start Emulators
        sdk_root = get_android_sdk_root()
        emulator_bin = shutil.which("emulator")
        if not emulator_bin and sdk_root:
             emulator_bin = os.path.join(sdk_root, "emulator", "emulator")
        
        if not emulator_bin: return "Error: Emulator binary not found."

        print(f"Starting {len(device_list)} Android emulators...")
        for avd in device_list:
            subprocess.Popen([emulator_bin, "@" + avd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Wait for boot (simple sleep for now, could be smarter)
        print("Waiting 45s for emulators to boot...")
        time.sleep(45)

        # 3. Get connected devices
        adb_bin = shutil.which("adb")
        if not adb_bin and sdk_root:
            adb_bin = os.path.join(sdk_root, "platform-tools", "adb")
            
        if adb_bin:
            res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True)
            lines = res.stdout.strip().split('\n')[1:]
            for line in lines:
                if "\tdevice" in line:
                    started_udids.append(line.split('\t')[0])
        
    elif platform_name.lower() == 'ios':
        if not is_mac(): return "Error: iOS requires macOS."
        
        # 1. Resolve Names to UUIDs and Boot
        cmd = ["xcrun", "simctl", "list", "devices", "available", "-j"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout)
        
        # Flatten the list
        available_sims = {}
        for runtime, devices in data.get("devices", {}).items():
            for d in devices:
                available_sims[d['name']] = d['udid']
        
        for name in device_list:
            udid = available_sims.get(name)
            if not udid:
                # Maybe the user passed a UUID
                if "-" in name and len(name) > 20: 
                    udid = name
                else:
                    return f"Error: Simulator '{name}' not found."
            
            subprocess.run(["xcrun", "simctl", "boot", udid], check=False)
            started_udids.append(udid)
            
        # Wait a bit for boot
        time.sleep(10)

    if not started_udids:
        return "Error: No devices available to run tests."

    # 4. Run Tests in Parallel
    processes = []
    
    print(f"Running tests on: {started_udids}")
    
    for udid in started_udids:
        # Replace placeholder
        cmd_str = test_command_pattern.replace("{udid}", udid)
        # Run command
        p = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append((udid, p))

    # 5. Collect Results
    output_report = "Parallel Execution Results:\n"
    for udid, p in processes:
        stdout, stderr = p.communicate()
        status = "PASSED" if p.returncode == 0 else "FAILED"
        output_report += f"\nDevice: {udid} | Status: {status}\n"
        output_report += f"Command: {test_command_pattern.replace('{udid}', udid)}\n"
        if p.returncode != 0:
            output_report += f"Error Output: {stderr[:200]}...\n"
            
    return output_report


if __name__ == "__main__":
    mcp.run()