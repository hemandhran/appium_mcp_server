# Appium MCP Server

This project provides a server with a set of tools to control and interact with Appium, Android emulators, and iOS simulators.

## Prerequisites

Before running the server, ensure you have the following installed and configured:

- **Python 3.x**
- **Node.js and npm**
- **Appium:**
  ```bash
  npm install -g appium
  ```
- **Android SDK:**
  - Set the `ANDROID_HOME` or `ANDROID_SDK_ROOT` environment variable.
  - Ensure the Android emulator is installed and configured.
- **For iOS (macOS only):**
  - **Xcode:** Install from the Mac App Store.
  - **Xcode Command Line Tools:**
    ```bash
    xcode-select --install
    ```
  - **WebDriverAgent:**
    - Appium's WebDriverAgent needs to be configured and signed with a valid developer account to run on physical devices.
    - For simulators, this is usually handled automatically by Appium.
    - Refer to the [Appium XCUITest Driver documentation](https://appium.io/docs/en/drivers/ios-xcuitest/) for detailed setup instructions.
  - **Build Settings:**
    - When using the `build_and_install_ios_app` tool, ensure your Xcode project's build settings are correctly configured for the target simulator and SDK.

## Features

- Start and stop the Appium server.
- List available Android AVDs and iOS Simulators.
- Start Android emulators and iOS simulators.
- Build and install iOS apps.
- Scaffold a BDD framework structure.
- Extract page locators from an active Appium session.

## Usage

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the server:**
    ```bash
    python appium_mcp_server.py
    ```

The server will then be running and ready to accept commands.
