import re
from typing import Optional, Callable
import litellm
from smolagents import ToolCallingAgent, LogLevel, PlanningStep, ActionStep, TaskStep
from smolagents.models import LiteLLMModel
from macllm.core.llm_service import MODELS
from macllm import tools as tools_module
from macllm.tools.web_search import reset_search_counter

litellm.drop_params = True


def extract_section(lines, start_pattern, stop_level):
    """Extract a section from plan text based on markdown headers."""
    section, collecting = [], False
    for line in lines:
        if line.startswith(stop_level) and not line.startswith(stop_level + '#'):
            if re.search(start_pattern, line, re.IGNORECASE):
                collecting, section = True, [line]
            elif collecting:
                break
        elif collecting:
            if not line.strip():
                break
            section.append(line)
    return section


def create_step_callback(token_callback: Optional[Callable[[int, int], None]] = None):
    """Create a callback for smolagents step events.
    
    Updates AgentStatusManager with plan, facts, and tool call information.
    """
    input_tokens = [0]
    output_tokens = [0]
    
    def on_step(step, agent):
        from macllm.macllm import MacLLM
        status_manager = MacLLM.get_status_manager()
        
        if isinstance(step, PlanningStep):
            if step.plan:
                lines = step.plan.split('\n')
                
                # Extract facts
                facts_lines = extract_section(lines, r'Facts.*learned', '###')
                if facts_lines:
                    facts_lines[0] = ""  # Remove header
                    facts_text = '\n'.join(line for line in facts_lines if line.strip())
                    if facts_text:
                        status_manager.set_facts(facts_text)
                
                # Extract plan
                plan_lines = extract_section(lines, r'2\.\s*Plan', '##')
                if plan_lines:
                    plan_lines[0] = ""  # Remove header
                    plan_lines = [line.lstrip('# ') for line in plan_lines]
                    plan_text = '\n'.join(line for line in plan_lines if line.strip())
                    if plan_text:
                        status_manager.set_plan(plan_text)
            
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
        
        elif isinstance(step, ActionStep):
            # Tool status updates are handled by the tools themselves
            # via MacLLM.get_status_manager().start_tool_call() and complete_tool_call()
            
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
        
        elif isinstance(step, TaskStep):
            # TaskStep handling - could be extended in future
            pass
    
    return on_step


def create_agent(model: Optional[LiteLLMModel] = None, speed: str = "normal", token_callback: Optional[Callable[[int], None]] = None) -> ToolCallingAgent:
    """Create a smolagents ToolCallingAgent with configured tools and callbacks."""
    # Reset search counter for new agent run
    reset_search_counter()
    
    if model is None:
        model = MODELS.get(speed.lower(), MODELS['normal'])
        if model is None:
            raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")
    
    tools = [getattr(tools_module, name) for name in tools_module.__all__]
    
    step_callback = create_step_callback(token_callback)
    
    from macllm.macllm import SYSTEM_PROMPT
    agent = ToolCallingAgent(
        tools=tools,
        model=model,
        instructions=SYSTEM_PROMPT,
        verbosity_level=LogLevel.ERROR,
        planning_interval=3,
        step_callbacks={
            PlanningStep: step_callback,
            ActionStep: step_callback,
            TaskStep: step_callback,
        },
    )
    
    return agent
