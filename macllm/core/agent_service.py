import re
from typing import Optional, Callable
from smolagents import PlanningStep, ActionStep, TaskStep


def extract_section(lines, start_pattern, stop_level):
    """Extract a section from plan text based on markdown headers."""
    section, collecting, has_content = [], False, False
    for line in lines:
        if line.startswith(stop_level) and not line.startswith(stop_level + '#'):
            if re.search(start_pattern, line, re.IGNORECASE):
                collecting, section, has_content = True, [line], False
            elif collecting:
                break
        elif collecting:
            if not line.strip():
                if has_content:
                    break
                continue
            has_content = True
            section.append(line)
    return section


def create_step_callback(token_callback: Optional[Callable[[int, int], None]] = None):
    """Create a callback for smolagents step events.
    
    Updates AgentStatusManager with plan, facts, and tool call information.
    Used by :class:`MacLLMAgent` during ``__init__``.
    """
    input_tokens = [0]
    output_tokens = [0]
    
    def on_step(step, agent):
        from macllm.macllm import MacLLM
        status_manager = MacLLM.get_status_manager()
        
        if isinstance(step, PlanningStep):
            if step.plan:
                lines = step.plan.split('\n')
                
                facts_lines = extract_section(lines, r'Facts.*learned', '###')
                if facts_lines:
                    facts_lines[0] = ""
                    facts_text = '\n'.join(line for line in facts_lines if line.strip())
                    if facts_text:
                        status_manager.set_facts(facts_text)
                
                plan_lines = extract_section(lines, r'2\.\s*Plan', '##')
                if plan_lines:
                    plan_lines[0] = ""
                    plan_lines = [line.lstrip('# ') for line in plan_lines]
                    plan_text = '\n'.join(line for line in plan_lines if line.strip())
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
