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
  - Ensure the Android emulator and ADB are installed and configured.
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

- **Appium Server Management:**
  - Start and stop the Appium server.
- **Device Management:**
  - List available Android AVDs (emulators).
  - List connected physical Android devices.
  - List available iOS Simulators.
  - List connected physical iOS devices.
  - Start Android emulators and iOS simulators.
- **Application Management:**
  - Build and install iOS apps from Xcode projects.
  - Launch and install apps on both Android and iOS.
- **Test Framework Tools:**
  - Scaffold a BDD framework structure.
  - Extract page locators from an active Appium session and generate Java Page Object classes.
  - **Self-healing:** Suggest new locators for elements based on visible text if the original locator is stale.

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

## Integrating with an MCP Client (e.g., in VS Code)

To use this server as an AI agent in your editor, you need to configure your MCP client to launch it. Here’s an example of how to do that.

1.  **Find your MCP client's configuration file.** This is often a `settings.json` or `mcp.json` file located in your editor's user settings directory.

2.  **Add a new server configuration.** You will need to provide the command to run the Python script. See the `mcp_config_example.json` file in this repository for a template.

    **Example Configuration:**
    ```json
    {
      "mcpServers": {
        "appium-mcp": {
          "command": "python",
          "args": [
            "/absolute/path/to/Appium_MCP/appium_mcp_server.py"
          ],
          "env": {
            "ANDROID_HOME": "/Users/yourusername/Library/Android/sdk"
          }
        }
      }
    }
    ```

    **Important:**
    - Replace `/absolute/path/to/Appium_MCP/appium_mcp_server.py` with the actual absolute path to the script on your machine.
    - Ensure the `ANDROID_HOME` environment variable is set correctly for your system.

3.  **Restart your editor** to ensure the new agent is loaded.

You should now be able to interact with the Appium MCP server through your AI assistant.
