import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        # Use the Python interpreter from the local virtual environment
        import sys
        import os
        
        if is_python:
            # Get the path to the current Python interpreter in the virtual environment
            python_path = sys.executable
            command = python_path
        else:
            command = "node"
        
        # Get the current environment variables
        env = dict(os.environ)
        
        # Add the virtual environment's Python path to PYTHONPATH
        venv_site_packages = os.path.join(os.path.dirname(python_path), '..', 'lib', 'python{}.{}'.format(
            sys.version_info.major, sys.version_info.minor), 'site-packages')
        
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{venv_site_packages}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = venv_site_packages
        
        # Force UTF-8 encoding for stdin/stdout
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Set additional environment variables to ensure proper encoding
        if os.name == 'nt':  # Windows
            env['PYTHONLEGACYWINDOWSSTDIO'] = '0'
            os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=env
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        messages = [
            {
                "role": "user",
                "content": [{"text": query}]
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "toolSpec": {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "json": tool.inputSchema
                }
            }
        } for tool in response.tools]

        system_prompt = [{"text": "You are a helpful AI assistant."}]
        inference_config = {
            "temperature": 0,
            "maxTokens": 2048,
            "topP": 0,
        }

        # Initial Bedrock API call
        try:
            response = self.bedrock.converse(
                modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
                messages=messages,
                system=system_prompt,
                toolConfig={"tools": available_tools},
                inferenceConfig=inference_config,
            )
        except ClientError as e:
            print(f"Bedrock API error: {str(e)}")
            return "Error calling Bedrock API"

        # After getting the initial response, add it to messages
        output_message = response.get("output", {}).get("message", {})
        messages.append({
            "role": "assistant",
            "content": output_message.get("content", [])
        })

        # Process response and handle tool calls
        tool_results = []
        final_text = []

        output_message = response.get("output", {}).get("message", {})
        content_list = output_message.get("content", [])

        for content in content_list:
            if "text" in content:
                final_text.append(content["text"])
            elif "toolUse" in content:
                tool_use = content["toolUse"]
                tool_name = tool_use["name"]
                tool_args = tool_use["input"]
                
                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Add this before creating the tool_result
                if hasattr(result, 'content'):
                    result_content = result.content if isinstance(result.content, str) else str(result.content)
                else:
                    result_content = str(result)

                tool_result = {
                    "toolUseId": tool_use["toolUseId"],
                    "content": [{"text": result_content}]
                }
                
                messages.append({
                    "role": "user",
                    "content": [{"toolResult": tool_result}]
                })

                # Get next response from Bedrock
                try:
                    response = self.bedrock.converse(
                        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
                        messages=messages,
                        system=system_prompt,
                        toolConfig={"tools": available_tools},
                        inferenceConfig=inference_config,
                    )
                    output_message = response.get("output", {}).get("message", {})
                    # Add the assistant's response to the message history
                    messages.append({
                        "role": "assistant",
                        "content": output_message.get("content", [])
                    })
                    if "content" in output_message:
                        for content in output_message["content"]:
                            if "text" in content:
                                final_text.append(content["text"])
                except ClientError as e:
                    print(f"Bedrock API error: {str(e)}")
                    return "Error calling Bedrock API"

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())