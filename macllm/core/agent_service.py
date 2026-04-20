from typing import Optional, Callable
from smolagents import PlanningStep, ActionStep, TaskStep


def extract_plan(text: str) -> str:
    """Extract numbered plan steps from text using ### Plan: ... <end_plan> markers."""
    import re
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

    Accumulates token usage across steps and invokes *token_callback*
    so the UI can update the token counter.
    """
    input_tokens = [0]
    output_tokens = [0]
    
    def on_step(step, agent):
        if isinstance(step, (PlanningStep, ActionStep)):
            if step.token_usage and token_callback:
                input_tokens[0] += step.token_usage.input_tokens
                output_tokens[0] += step.token_usage.output_tokens
                token_callback(input_tokens[0], output_tokens[0])
    
    return on_step


def create_agent(agent_cls=None, speed="normal", token_callback=None):
    """Thin factory for creating agent instances."""
    if agent_cls is None:
        from macllm.agents import get_default_agent_class
        agent_cls = get_default_agent_class()
    return agent_cls(speed=speed, token_callback=token_callback)
