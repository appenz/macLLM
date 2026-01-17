import os
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


def create_step_callback(status_callback: Optional[Callable[[str], None]], token_callback: Optional[Callable[[int, int], None]] = None):
    input_tokens = [0]
    output_tokens = [0]
    
    def on_step(step, agent):
        status_lines = []
        
        if isinstance(step, PlanningStep):
            if step.plan:
                lines = step.plan.split('\n')
                progress = extract_section(lines, r'Facts.*learned', '###')
                plan = extract_section(lines, r'2\.\s*Plan', '##')
                
                if progress:
                    progress[0] = "Facts learned:"
                    status_lines.extend(progress)
                if plan:
                    plan[0] = "Plan:"
                    plan = [line.lstrip('# ') for line in plan]
                    status_lines.extend(plan)
            
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
        
        elif isinstance(step, ActionStep):
            tool_calls = []
            if step.tool_calls:
                tool_calls = [(tc.name, tc.arguments) for tc in step.tool_calls]
            elif step.model_output_message and step.model_output_message.tool_calls:
                tool_calls = [
                    (tc.function.name, tc.function.arguments) if hasattr(tc, 'function') 
                    else (str(tc), None)
                    for tc in step.model_output_message.tool_calls
                ]
            
            if tool_calls:
                status_lines.append("Using tools:")
                for name, args in tool_calls:
                    if args:
                        if name == "web_search":
                            queries = args.get('queries', [])
                            queries_str = ', '.join(f"'{q}'" for q in queries[:3])
                            if len(queries) > 3:
                                queries_str += f" (+{len(queries) - 3} more)"
                            status_lines.append(f"- Tool Call: web_search: {queries_str}")
                        elif name == "final_answer":
                            status_lines.append(f"- final_answer: '{args['answer']}'")
                        else:
                            args_str = str(args)[:60]
                            status_lines.append(f"- Tool Call: {name}({args_str})")
                    else:
                        status_lines.append(f"- Tool Call: {name}")
            
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
        
        elif isinstance(step, TaskStep):
            status_lines.append("Task:")
            status_lines.append(str(step))
        
        if status_lines and status_callback:
            status_text = '\n'.join(status_lines)
            status_callback(status_text)
    
    return on_step


def create_agent(model: Optional[LiteLLMModel] = None, speed: str = "normal", status_callback: Optional[Callable[[str], None]] = None, token_callback: Optional[Callable[[int], None]] = None) -> ToolCallingAgent:
    # Reset search counter for new agent run
    reset_search_counter()
    
    if model is None:
        model = MODELS.get(speed.lower(), MODELS['normal'])
        if model is None:
            raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")
    
    tools = [getattr(tools_module, name) for name in tools_module.__all__]
    
    step_callback = create_step_callback(status_callback, token_callback)
    
    agent = ToolCallingAgent(
        tools=tools,
        model=model,
        verbosity_level=LogLevel.ERROR,
        planning_interval=3,
        step_callbacks={
            PlanningStep: step_callback,
            ActionStep: step_callback,
            TaskStep: step_callback,
        },
    )
    
    return agent
