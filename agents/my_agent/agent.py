from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools import agent_tool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context

cgm_agent_google_search_agent = LlmAgent(
  name='CGM_Agent_google_search_agent',
  model='gemini-2.5-pro',
  description=(
      'Agent specialized in performing Google searches.'
  ),
  sub_agents=[],
  instruction='Use the GoogleSearchTool to find information on the web.',
  tools=[
    GoogleSearchTool()
  ],
)
cgm_agent_url_context_agent = LlmAgent(
  name='CGM_Agent_url_context_agent',
  model='gemini-2.5-pro',
  description=(
      'Agent specialized in fetching content from URLs.'
  ),
  sub_agents=[],
  instruction='Use the UrlContextTool to retrieve content from provided URLs.',
  tools=[
    url_context
  ],
)
root_agent = LlmAgent(
  name='CGM_Agent',
  model='gemini-2.5-pro',
  description=(
      'Agent for providing advice for glucose monitoring'
  ),
  sub_agents=[],
  instruction='You are a custom agent to help me manage my type one diabetes. I want you to provide guidance to help me keep my blood sugar in range, by suggesting lifestyle steps, activity changes, food choices, etc.',
  tools=[
    agent_tool.AgentTool(agent=cgm_agent_google_search_agent),
    agent_tool.AgentTool(agent=cgm_agent_url_context_agent),
    McpToolset(
      connection_params=StreamableHTTPConnectionParams(
        url='https://cgm-app-mcp-303011899435.europe-west1.run.app/',
      ),
    )
  ],
)