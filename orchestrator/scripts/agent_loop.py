#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path

from common import (
    ROOT,
    PROMPTS_DIR,
    print_phase,
    print_header,
    ProgressIndicator,
    prompt_input,
)
from llm import run_llm, extract_json_block
from model_router import ModelRole

def run_streaming_shell(command: str, cwd: Path) -> tuple[str, int]:
    """Runs a shell command and streams its output to the console in real-time."""
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(cwd),
        env=os.environ.copy()
    )
    
    output_lines = []
    sel = selectors.DefaultSelector()
    if process.stdout:
        sel.register(process.stdout, selectors.EVENT_READ)
    
    try:
        while process.poll() is None:
            for key, _ in sel.select(timeout=0.1):
                line = key.fileobj.readline()
                if line:
                    print(f"    \033[90m[shell]\033[0m {line}", end="", flush=True)
                    output_lines.append(line)
                    
        # Final read
        if process.stdout:
            for line in process.stdout:
                print(f"    \033[90m[shell]\033[0m {line}", end="", flush=True)
                output_lines.append(line)
    finally:
        sel.close()
    
    return "".join(output_lines), process.returncode

def main() -> int:
    parser = argparse.ArgumentParser(description="Agentic Orchestration Loop POC")
    parser.add_argument("goal", help="The high-level goal for the Lead Agent")
    parser.add_argument("--model", default="gemini", help="Model to use for the Lead Agent")
    parser.add_argument("--max-turns", type=int, default=5, help="Maximum number of orchestration turns")
    parser.add_argument("--confirm", action="store_true", help="Prompt for confirmation before running 'dangerous' tools (shell, dispatch)")
    parser.add_argument("--step-by-step", action="store_true", help="Pause after each turn for review")
    parser.add_argument("--yolo", action="store_true", help="Skip all review phases and confirmations (fully autonomous)")
    args = parser.parse_args()

    lead_prompt_path = PROMPTS_DIR / "agent_lead.md"
    if not lead_prompt_path.exists():
        print(f"Error: Lead prompt not found at {lead_prompt_path}")
        return 1
    
    lead_prompt = lead_prompt_path.read_text(encoding="utf-8")
    
    history = []
    current_input = f"USER GOAL: {args.goal}"
    
    print_header("Agentic Orchestration Starting")
    print(f"Goal: {args.goal}\n")

    for turn in range(1, args.max_turns + 1):
        print(f"\n\033[1;95m" + "="*60)
        print(f" TURN {turn} | STATUS: \033[1;97mAGENT THINKING\033[0m")
        print("="*60 + "\033[0m")
        
        full_prompt = f"{lead_prompt}\n\n{current_input}"
        if history:
            full_prompt += "\n\n### CONVERSATION HISTORY ###\n" + "\n".join(history)

        with ProgressIndicator(f"Consulting {args.model}..."):
            llm_output, actual_model, session_id = run_llm(args.model, full_prompt, role=ModelRole.PLANNER, stream=True)
        
        print("\033[0m") # Reset color and ensure newline after stream
        
        try:
            response = json.loads(extract_json_block(llm_output))
        except Exception as e:
            print(f"\n\033[1;91m[STATUS] ERROR: FAILED TO PARSE RESPONSE\033[0m")
            print(f"Details: {e}")
            print("-" * 40)
            print(llm_output)
            print("-" * 40)
            return 1

        if response.get("status") == "completed":
            print(f"\n\033[1;92m" + "="*60)
            print(f" STATUS: GOAL COMPLETED")
            print("="*60 + "\033[0m")
            print(f"\033[1;97mFinal Response:\033[0m {response.get('final_response')}")
            return 0
        
        if response.get("status") == "clarification-needed":
            print(f"\n\033[1;93m" + "="*60)
            print(f" STATUS: USER INPUT REQUIRED (CLARIFICATION)")
            print("="*60 + "\033[0m")
            print(f"\033[1;97mQuestion:\033[0m {response.get('clarification')}")
            
            user_answer = prompt_input("Your Answer:", placeholder="(required)")
            if not user_answer:
                print("No answer provided. Stopping.")
                return 0
                
            history.append(f"AGENT CLARIFICATION QUESTION: {response.get('clarification')}")
            history.append(f"USER ANSWER: {user_answer}")
            current_input = f"USER ANSWER TO CLARIFICATION: {user_answer}\n\nPlease proceed with this information."
            continue

        actions = response.get("actions", [])
        if not actions:
            # Check for legacy 'delegations' for backward compatibility during transition
            delegations = response.get("delegations", [])
            if delegations:
                actions = [{"type": "delegate", **d} for d in delegations]
            else:
                print("\033[1;91m[STATUS] ERROR: NO ACTIONS PROVIDED\033[0m")
                return 0

        # --- PLAN REVIEW PHASE ---
        if not args.yolo:
            print(f"\n\033[1;93m" + "="*60)
            print(f" STATUS: USER INPUT REQUIRED (PLAN REVIEW)")
            print("="*60 + "\033[0m")
            print(f"\033[1;97mThought:\033[0m {response.get('thought')}")
            print(f"\n\033[1;97m📋 PROPOSED ACTIONS:\033[0m")
            for i, action in enumerate(actions):
                a_type = action.get("type")
                if a_type == "delegate":
                    print(f"  {i+1}. [DELEGATE] \033[1;97m->\033[0m \033[1;97m{action.get('agent')}\033[0m: {action.get('instruction')}")
                elif action.get("tool"):
                    tool = action.get("tool")
                    args_val = action.get("args")
                    print(f"  {i+1}. [TOOL]     \033[1;97m->\033[0m \033[1;97m{tool}\033[0m: {json.dumps(args_val)}")

            print("\n\033[1;97mChoices:\033[0m")
            print("  [\033[92mA\033[0m] Approve & Run All")
            print("  [\033[93mF\033[0m] Provide Feedback (Steer the Agent)")
            print("  [\033[91mQ\033[0m] Abort / Quit")
            
            from orchestrator.scripts.common import get_key
            print("\n  \033[1;97mChoice:\033[0m ", end="", flush=True)
            user_choice = get_key().strip().lower()

            if user_choice == "q":
                print("\033[91mabort\033[0m")
                print("\nAborting orchestration loop.")
                return 0
            elif user_choice == "f":
                print("\033[93mfeedback\033[0m")
                feedback = prompt_input("Feedback for Agent:", placeholder="(or Enter to cancel)")
                if feedback:
                    history.append(f"USER FEEDBACK (TURN {turn}): {feedback}")
                    current_input = f"USER FEEDBACK: {feedback}\n\nPlease revise your plan based on this feedback."
                    continue
                else:
                    print("  No feedback provided. Cancelling turn.")
                    return 0
            elif user_choice in {"a", "enter"}:
                print("\033[92mapprove\033[0m")
            else:
                print(f"\033[91m{user_choice}\033[0m")
                print("  Invalid choice. Aborting for safety.")
                return 0
        print(f"\n\033[1;92m" + "-"*60)
        print(f" STATUS: EXECUTING APPROVED PLAN")
        print("-"*60 + "\033[0m")

        turn_results = []
        for i, action in enumerate(actions):
            action_type = action.get("type")
            
            if action_type == "delegate":
                agent_name = action.get("agent")
                instruction = action.get("instruction")
                print(f"\n\033[1;97m[ACTION] Delegating to sub-agent '{agent_name}'...\033[0m")
                print(f"Instruction: {instruction}")
                
                sub_prompt_path = PROMPTS_DIR / f"{agent_name}.md"
                if not sub_prompt_path.exists():
                    res = f"ERROR: Sub-agent prompt '{agent_name}.md' not found."
                    print(f"\033[91m{res}\033[0m")
                    turn_results.append(f"Sub-agent {agent_name} result: {res}")
                    continue
                
                sub_prompt = sub_prompt_path.read_text(encoding="utf-8")
                sub_input = f"{sub_prompt}\n\nINSTRUCTION: {instruction}"
                
                with ProgressIndicator(f"Running {agent_name}..."):
                    sub_output, actual_model, session_id = run_llm(args.model, sub_input)
                
                print(f"Result from {agent_name} received.")
                turn_results.append(f"### Result from sub-agent {agent_name} ###\n{sub_output}")

            elif action_type == "tool":
                tool_name = action.get("tool")
                args_dict = action.get("args", {})
                
                # Safeguard: Confirm dangerous tools
                if not args.yolo and args.confirm and tool_name in ["shell", "dispatch"]:
                    print(f"\n\033[1;93m⚠️  CONFIRMATION REQUIRED for tool '{tool_name}':\033[0m")
                    if tool_name == "shell":
                        print(f"  Command: \033[97m{args_dict.get('command')}\033[0m")
                    elif tool_name == "dispatch":
                        print(f"  Job Goal: \033[97m{args_dict.get('goal')}\033[0m")
                    
                    from orchestrator.scripts.common import get_key
                    print(f"\n  Proceed? (y/n): ", end="", flush=True)
                    user_ok = get_key().strip().lower()
                    if user_ok not in {"y", "yes"}:
                        print("\033[91mno\033[0m")
                        print("  Skipping tool execution.")
                        turn_results.append(f"### Result from system tool {tool_name} ###\nUSER CANCELLED: Execution was denied by the user.")
                        continue
                    print("\033[92myes\033[0m")

                print(f"\n\033[1;97m[ACTION] Executing system tool '{tool_name}'...\033[0m")
                
                tool_result = ""
                try:
                    if tool_name == "ls":
                        path = Path(args_dict.get("path", "."))
                        if not path.is_absolute(): path = ROOT / path
                        files = sorted([str(p.relative_to(ROOT)) for p in path.glob("*") if not p.name.startswith(".")])
                        tool_result = "\n".join(files) or "(empty directory)"
                        print(f"    \033[90m[files]\033[0m " + ", ".join(files[:20]) + ("..." if len(files) > 20 else ""))
                    elif tool_name == "read":
                        path = Path(args_dict.get("path", ""))
                        if not path.is_absolute(): path = ROOT / path
                        tool_result = path.read_text(encoding="utf-8")
                        print(f"    \033[90m[read]\033[0m {path.name} ({len(tool_result)} chars)")
                    elif tool_name == "grep":
                        pattern = args_dict.get("pattern", "")
                        cmd = f"grep -r {shlex.quote(pattern)} {shlex.quote(str(ROOT))}"
                        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        tool_result = res.stdout or res.stderr or "(no matches)"
                        print(f"    \033[90m[grep]\033[0m found {len(tool_result.splitlines())} matches for '{pattern}'")
                    elif tool_name == "shell":
                        command = args_dict.get("command", "")
                        print(f"  $ {command}")
                        tool_result, exit_code = run_streaming_shell(command, ROOT)
                        tool_result = f"OUTPUT:\n{tool_result}\nEXIT CODE: {exit_code}"
                    elif tool_name == "dispatch":
                        job_type = args_dict.get("job_type", "feature")
                        goal = args_dict.get("goal", "")
                        print(f"  Dispatching {job_type} job: {goal}")
                        tool_result = f"SUCCESS: {job_type} job created and scheduled for goal: {goal}"
                    else:
                        tool_result = f"ERROR: Unknown tool '{tool_name}'"
                except Exception as e:
                    tool_result = f"ERROR executing tool {tool_name}: {e}"

                print(f"Tool '{tool_name}' execution finished.")
                turn_results.append(f"### Result from system tool {tool_name} ###\n{tool_result}")

        # Update history and prepare next turn input
        history.append(f"TURN {turn} THOUGHT: {response.get('thought')}")
        history.append(f"TURN {turn} ACTIONS: {json.dumps(actions)}")
        
        current_input = "### ACTION RESULTS ###\n" + "\n\n".join(turn_results)
        current_input += "\n\nPlease analyze these results and decide on the next steps."

        if args.step_by_step and turn < args.max_turns:
            input(f"\n\033[1;96mTurn {turn} complete. Tap Enter to continue to next turn...\033[0m")

    print(f"\n\033[91mReached maximum turns ({args.max_turns}). Stopping.\033[0m")
    return 0

import shlex
if __name__ == "__main__":
    sys.exit(main())
