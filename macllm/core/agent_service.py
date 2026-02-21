import re
from typing import Optional, Callable
from smolagents import PlanningStep, ActionStep, TaskStep


def extract_plan(text: str) -> str:
    """Extract numbered plan steps from text using ### Plan: ... <end_plan> markers."""
    lines = text.split('\n')
    collecting = False
    plan_lines: list[str] = []
    for line in lines:
        if re.match(r'^###\s+Plan\s*:', line):
            collecting = True
            continue
        if collecting:
            if '<end_plan>' in line:
                break
            stripped = line.strip()
            if stripped and stripped.strip('`') != '':
                plan_lines.append(line)
    return '\n'.join(plan_lines)


def create_step_callback(token_callback: Optional[Callable[[int, int], None]] = None):
    """Create a callback for smolagents step events.
    
    Updates AgentStatusManager with plan and tool call information.
    Used by :class:`MacLLMAgent` during ``__init__``.
    """
    input_tokens = [0]
    output_tokens = [0]
    
    def on_step(step, agent):
        from macllm.macllm import MacLLM
        status_manager = MacLLM.get_status_manager()
        
        if isinstance(step, PlanningStep):
            if step.plan:
                plan_text = extract_plan(step.plan)
                if plan_text:
                    status_manager.set_plan(plan_text)
            
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
        
        elif isinstance(step, ActionStep):
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
        
        elif isinstance(step, TaskStep):
            pass
    
    return on_step


def create_agent(agent_cls=None, speed="normal", token_callback=None):
    """Thin factory for creating agent instances.

    Kept as a module-level function so tests can easily patch it.
    """
    if agent_cls is None:
        from macllm.agents import get_default_agent_class
        agent_cls = get_default_agent_class()
    return agent_cls(speed=speed, token_callback=token_callback)
