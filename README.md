# MCP Anthropic Integration

This repository contains a Model Context Protocol (MCP) for Anthropic's Claude Desktop application, featuring a weather service example.

## Requirements

- UV (Python package manager)
- Claude Desktop (if want to use the tools in with anthropic chat UI)
- Python >= 3.10
- Anthropic API key (for client.py)
- AWS credentials (for bedrockClient.py)

## Setup Instructions

### 1. Client Setup

The project includes two client implementations:

1. **Anthropic API Client** (`client.py`): Uses the standard Anthropic API
2. **AWS Bedrock Client** (`bedrockClient.py`): Uses AWS Bedrock for Claude integration

To run either client:

```bash
cd mcp-client
uv venv   # Create virtual environment using uv
uv pip install -e .   # Install the client package

# For Anthropic API client
uv run client.py path/to/server/weather/server.py

# For AWS Bedrock client
uv run bedrockClient.py path/to/server/weather/server.py
```

### 2. Server Setup

```bash
cd weather-server-python
uv venv   # Create virtual environment
```

### 3. Claude Desktop Configuration

1. Install Claude Desktop from Anthropic
2. Open the configuration file:

```bash
code %AppData%\Claude\claude_desktop_config.json
```

3. Add the following configuration (adjust the path according to your setup):

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather",
        "run",
        "weather"
      ]
    }
  }
}
```

## Usage

Once configured, the weather tools will be available in Claude Desktop. You can interact with them directly through the Claude interface.

## Custom Tools

You can extend the functionality by adding more tools to your custom server. Update the `claude_desktop_config.json` accordingly to make new tools available in Claude Desktop.

> ⚠️ **Important**: When naming your tools, only use letters, numbers, and underscores (\_). Special characters and spaces are not supported in tool names.
