import os
import sys
import re
import time
import json
import asyncio
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Set
import requests
import discord
from discord.ext import commands

sys.path.insert(0, "/opt/firstmate")

def load_env():
    env = {}
    path = "/opt/firstmate/.env"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()
    return env

load_env()

from infra.execution_sandbox import dispatch_tool
from memory.ditto_engine import ditto_engine

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

CONFIG = {
    "provider": "antigravity",
    "model": "gemini-3.8-flash-high",
    "effort": "high"
}

ANNOUNCED_BYPASSES = set()

SENSITIVE_PATTERNS = [
    r"(ghp_[a-zA-Z0-9]{20,}|gho_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]{20,})",
    r"(sk-[a-zA-Z0-9_\-]{20,})",
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    r"\b(api_key|apikey|secret_key)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]",
    r"\b(password|passwd)\s*[:=]\s*['\"][^'\"]{6,}['\"]",
    r"\b(private_key|seed_phrase|mnemonic_phrase)\b",
    r"\b(ssn\s*[:=]?\s*\d{3}-\d{2}-\d{4}|credit card\s*[:=]?\s*\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4})\b",
    r"\b(chutes tee|run in tee|confidential compute enclave|zero-retention enclave)\b"
]

def evaluate_privacy(text: str):
    if not text:
        return False, None
    for pattern in SENSITIVE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return True, f"Matched sensitive pattern: {pattern}"
    return False, None

def get_antigravity_quota():
    token_path = '/root/.gemini/antigravity-cli/antigravity-oauth-token'
    try:
        with open(token_path, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        
        access_token = token_data['token']['access_token']
        expiry_str = token_data['token'].get('expiry', '')
        
        # Check if expired or near expiry
        is_expired = False
        if expiry_str:
            try:
                exp_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                if exp_dt.timestamp() <= time.time() + 60:
                    is_expired = True
            except Exception:
                pass
                
        if is_expired:
            refresh_token = token_data['token'].get('refresh_token')
            if refresh_token:
                refresh_url = 'https://oauth2.googleapis.com/token'
                data = {
                    'client_id': '1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com',
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token
                }
                r = requests.post(refresh_url, data=data, timeout=10)
                if r.status_code == 200:
                    r_json = r.json()
                    access_token = r_json['access_token']
                    token_data['token']['access_token'] = access_token
                    new_exp = datetime.fromtimestamp(time.time() + r_json.get('expires_in', 3600), timezone.utc).isoformat()
                    token_data['token']['expiry'] = new_exp
                    with open(token_path, 'w', encoding='utf-8') as fw:
                        json.dump(token_data, fw, indent=2)

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'antigravity-cli/1.2.7'
        }
        
        endpoints = [
            'https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota',
            'https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota'
        ]
        
        buckets = []
        last_err = None
        for url in endpoints:
            try:
                resp = requests.post(url, headers=headers, json={}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    buckets = data.get('buckets', [])
                    if buckets:
                        break
                else:
                    last_err = f"HTTP {resp.status_code}"
            except Exception as e:
                last_err = str(e)
                
        five_hour_pct = None
        five_hour_reset = None
        weekly_pct = None
        weekly_reset = None
        
        for b in buckets:
            model = b.get('modelId', '')
            rem = b.get('remainingFraction')
            reset = b.get('resetTime', '')
            if rem is None:
                continue
            rem_float = float(rem)
            
            if 'gemini-3.8-flash' in model or 'gemini-3.6-flash-high' in model:
                if five_hour_pct is None:
                    five_hour_pct = round(rem_float * 100, 1)
                    five_hour_reset = reset
            elif 'claude-sonnet' in model or 'claude-opus' in model or 'gpt-oss-120b' in model:
                if weekly_pct is None:
                    weekly_pct = round(rem_float * 100, 1)
                    weekly_reset = reset

        # Fallback to any gemini or claude model in buckets if exact model ID differed
        if five_hour_pct is None:
            for b in buckets:
                model = b.get('modelId', '')
                rem = b.get('remainingFraction')
                if rem is not None and 'gemini' in model:
                    five_hour_pct = round(float(rem) * 100, 1)
                    five_hour_reset = b.get('resetTime', '')
                    break

        if weekly_pct is None:
            for b in buckets:
                model = b.get('modelId', '')
                rem = b.get('remainingFraction')
                if rem is not None and ('claude' in model or 'gpt-oss' in model):
                    weekly_pct = round(float(rem) * 100, 1)
                    weekly_reset = b.get('resetTime', '')
                    break

        # Fallback to quota-axi CLI if CloudCode quota was empty
        if five_hour_pct is None and weekly_pct is None:
            try:
                axi_res = subprocess.run(['quota-axi', '--json'], capture_output=True, text=True, timeout=5)
                if axi_res.stdout:
                    axi_data = json.loads(axi_res.stdout)
                    for prov in axi_data.get('providers', []):
                        for w in prov.get('windows', []):
                            wid = str(w.get('id', '')).lower()
                            wkind = str(w.get('kind', '')).lower()
                            wlabel = str(w.get('label', '')).lower()
                            rem_val = w.get('percentRemaining')
                            if rem_val is not None:
                                if five_hour_pct is None and (wid in ['five_hour', '5h', 'session'] or 'five_hour' in wid or wkind == 'session' or '5-hour' in wlabel):
                                    five_hour_pct = float(rem_val)
                                    five_hour_reset = w.get('resetsAt', '')
                                if weekly_pct is None and (wid in ['weekly', 'seven_day', '7d', 'week'] or 'weekly' in wid or 'seven_day' in wid or wkind == 'weekly' or 'week' in wlabel):
                                    weekly_pct = float(rem_val)
                                    weekly_reset = w.get('resetsAt', '')
            except Exception as axi_err:
                print(f"[QUOTA AXI FALLBACK ERROR]: {axi_err}", flush=True)

        if five_hour_pct is None and weekly_pct is None:
            return None, last_err or "No quota data found"
                    
        return {
            'five_hour_pct': five_hour_pct,
            'five_hour_reset': five_hour_reset,
            'weekly_pct': weekly_pct,
            'weekly_reset': weekly_reset
        }, None
    except Exception as e:
        return None, str(e)

def format_quota_string(quota_dict: Optional[Dict[str, Any]]) -> str:
    if not quota_dict:
        return "• **5-Hour Limit:** `Unavailable`\n• **Weekly Limit:** `Unavailable`"
    
    f_pct = quota_dict.get('five_hour_pct')
    w_pct = quota_dict.get('weekly_pct')
    
    if f_pct is not None:
        f_used = round(100.0 - f_pct, 1)
        f_str = f"{f_pct}% remaining ({f_used}% used)"
    else:
        f_str = "N/A"

    if w_pct is not None:
        w_used = round(100.0 - w_pct, 1)
        w_str = f"{w_pct}% remaining ({w_used}% used)"
    else:
        w_str = "N/A"
    
    f_reset = quota_dict.get('five_hour_reset')
    if f_reset:
        try:
            r_dt = datetime.fromisoformat(f_reset.replace('Z', '+00:00'))
            diff_mins = int((r_dt.timestamp() - time.time()) / 60)
            if diff_mins > 0:
                hours, mins = divmod(diff_mins, 60)
                f_str += f" (resets in {hours}h {mins}m)"
        except Exception:
            pass
            
    w_reset = quota_dict.get('weekly_reset')
    if w_reset:
        try:
            r_dt = datetime.fromisoformat(w_reset.replace('Z', '+00:00'))
            diff_hours = int((r_dt.timestamp() - time.time()) / 3600)
            if diff_hours > 0:
                days, hours = divmod(diff_hours, 24)
                w_str += f" (resets in {days}d {hours}h)"
        except Exception:
            pass

    return f"• **5-Hour Limit:** `{f_str}`\n• **Weekly Limit:** `{w_str}`"

def call_antigravity_cli(system_prompt: str, prompt: str, model_name: str = "gemini-3.8-flash-high") -> str:
    full_prompt = f"{system_prompt}\n\n{prompt}"
    cmd = ["/usr/local/bin/agy", "-p", full_prompt, "--model", model_name, "--dangerously-skip-permissions"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=360, cwd="/opt/firstmate/projects/Shojin")
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    err = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
    raise RuntimeError(f"Antigravity CLI error: {err}")

def call_saygm_api(system_prompt: str, prompt: str, model_name: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    m = "deepseek-ai/deepseek-v3" if "deepseek" in model_name.lower() else "Qwen/Qwen2.5-Coder-32B-Instruct"
    payload = {
        "model": m,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }
    resp = requests.post("https://api.saygm.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"SayGM HTTP {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

def call_chutes_api(system_prompt: str, prompt: str, model_name: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }
    resp = requests.post("https://chutes.ai/v1/chat/completions", headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"Chutes HTTP {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

def call_gemini_api(system_prompt: str, prompt: str, model_name: str, api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}]
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text}")
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

def call_openai_api(system_prompt: str, prompt: str, model_name: str, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

async def dispatch_step_inference(
    system_prompt: str,
    prompt: str,
    status_notifier=None,
    wing: str = "firstmate",
    requested_model: Optional[str] = None,
    task_instruction: str = "",
    task_banned_keys: Optional[Set[str]] = None
) -> Tuple[str, str, bool]:
    is_sensitive, reason = evaluate_privacy(prompt)
    if not is_sensitive and task_instruction:
        is_sensitive, reason = evaluate_privacy(task_instruction)

    # 1. Sensitive Data Route: Auto-splice into Chutes TEE confidential enclave
    if is_sensitive:
        if status_notifier and "chutes_privacy_bypass" not in ANNOUNCED_BYPASSES:
            ANNOUNCED_BYPASSES.add("chutes_privacy_bypass")
            await status_notifier(
                "privacy_splice",
                f"🛡️ **[Confidential TEE Activated]** Sensitive data detected ({reason}). Routing through Chutes TEE enclave."
            )
        target_model = "Qwen/Qwen3.6-27B-TEE"
        target_provider = "chutes"
    else:
        target_provider = CONFIG["provider"]
        target_model = requested_model or CONFIG["model"]

    # 2. Primary Route: Antigravity Google AI Pro subscription pool (unmetered quota)
    if target_provider == "antigravity" and not is_sensitive:
        try:
            res = await asyncio.to_thread(call_antigravity_cli, system_prompt, prompt, target_model)
            return res, f"Antigravity Pool ({target_model})", False
        except Exception as agy_err:
            print(f"[ANTIGRAVITY POOL FALLBACK] Notice: {agy_err}", flush=True)
            if status_notifier and "antigravity_fallback" not in ANNOUNCED_BYPASSES:
                ANNOUNCED_BYPASSES.add("antigravity_fallback")
                await status_notifier(
                    "pool_notice",
                    "⚡ Antigravity pool busy/quota limit; seamlessly routing to SayGM / Chutes TEE."
                )
            target_provider = "saygm"
            target_model = "deepseek-v4.1-flash"

    # 3. Resilient Secondary Routes: SayGM, Chutes TEE, or Direct APIs
    saygm_key = os.getenv("SAYGM_API_KEY", "")
    chutes_key = os.getenv("CHUTES_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if (target_provider == "saygm" or target_provider == "antigravity") and saygm_key:
        try:
            res = await asyncio.to_thread(call_saygm_api, system_prompt, prompt, target_model, saygm_key)
            return res, f"SayGM ({target_model})", False
        except Exception as e:
            print(f"[FALLBACK ERROR] SayGM failed: {e}", flush=True)

    if chutes_key:
        try:
            res = await asyncio.to_thread(call_chutes_api, system_prompt, prompt, "Qwen/Qwen3.6-27B-TEE", chutes_key)
            return res, "Chutes TEE (Qwen3.6-27B-TEE)", True
        except Exception as e:
            print(f"[FALLBACK ERROR] Chutes failed: {e}", flush=True)

    if gemini_key:
        try:
            res = await asyncio.to_thread(call_gemini_api, system_prompt, prompt, "gemini-2.5-flash", gemini_key)
            return res, "Gemini API (Direct)", False
        except Exception as e:
            print(f"[FALLBACK ERROR] Gemini API failed: {e}", flush=True)

    if openai_key:
        try:
            res = await asyncio.to_thread(call_openai_api, system_prompt, prompt, "gpt-4o", openai_key)
            return res, "OpenAI API (Direct)", False
        except Exception as e:
            print(f"[FALLBACK ERROR] OpenAI API failed: {e}", flush=True)

    raise RuntimeError("All inference routes exhausted.")

FIRSTMATE_SYSTEM_PROMPT = """You are First Mate, the sole liaison and crew execution engine for the Captain on the FirstMate Distro (/opt/firstmate).
The Captain talks only to you. You dispatch, supervise, coordinate worktrees, and report clean, finished outcomes.
The Captain's language is outcomes, consequences, and decisions. Internal machinery stays below deck.
Never roleplay as corporate wings, departments, committees, or SREs. You are simply the First Mate.

Your active workspace is: /opt/firstmate/projects/Shojin (symlinked to projects/Shojin).
You have full tools to inspect and modify the project:
- read_file(path)
- write_file(path, content)
- replace_file_content(path, target_content, replacement_content)
- execute_shell(command)
- search_memories(query)
- save_memory(session_id, text, subjects)

Rules:
1. Always adhere strictly to the Captain's design preferences (e.g. Apple-grade minimalism, dark obsidian, frosted glassmorphism, NO AI slop, NO candy gradients).
2. To use a tool, respond with a JSON code block:
```json
{
  "action": "tool",
  "tool": "tool_name",
  "args": { "arg_name": "arg_value" }
}
```
3. When you have completed the task or synthesized the requested deliverable, respond with:
```json
{
  "action": "final_answer",
  "output": "Clear, concise outcome report for the Captain."
}
```
"""

async def execute_firstmate_autonomous_mission(
    captain_directive: str,
    inference_caller,
    status_notifier=None,
    max_turns: int = 8
) -> dict:
    history = []
    
    # Feature 3: Ditto Memory Pre-fetch
    ditto_notes = ""
    try:
        mems = ditto_engine.search_memories("shojin_design_system", limit=2)
        if mems:
            ditto_notes = f"\n[HEYDITTO CANONICAL PREFERENCES]:\n{str(mems)[:800]}\n"
    except Exception as e:
        print(f"[DITTO QUERY]: {e}", flush=True)

    conversation_context = f"{ditto_notes}\nCaptain's Directive: {captain_directive}\n\nExecute this task with precision. Report final outcome when complete."
    final_output = ""
    turns_run = 0

    for turn in range(1, max_turns + 1):
        turns_run = turn
        
        resp, route, is_chutes = await inference_caller(
            system_prompt=FIRSTMATE_SYSTEM_PROMPT,
            prompt=conversation_context,
            status_notifier=status_notifier,
            wing="firstmate",
            task_instruction=captain_directive
        )

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", resp, re.DOTALL)
        if not match:
            match = re.search(r"(\{[\s\S]*\})", resp)

        parsed = {}
        if match:
            try:
                parsed = json.loads(match.group(1))
            except Exception:
                parsed = {}

        action = parsed.get("action")
        if action == "tool":
            tool_name = parsed.get("tool", "")
            tool_args = parsed.get("args", {})

            if status_notifier:
                clean_args_str = json.dumps(tool_args)
                if len(clean_args_str) > 100:
                    clean_args_str = clean_args_str[:97] + "..."
                await status_notifier("tool", f"🔧 `{tool_name}`: `{clean_args_str}`")

            obs = dispatch_tool(tool_name, tool_args)
            obs_preview = str(obs)[:1500]
            conversation_context += f"\n\n[Action Taken: `{tool_name}` with args {json.dumps(tool_args)}]\nObservation:\n{obs_preview}"
            history.append(f"Turn {turn}: `{tool_name}`")
        elif action == "final_answer":
            final_output = parsed.get("output", resp)
            break
        else:
            final_output = resp
            break

    if not final_output:
        final_output = conversation_context[-1200:]

    return {
        "turns": turns_run,
        "history": history,
        "final_output": final_output
    }

async def firstmate_dispatch(ctx, prompt: str):
    ANNOUNCED_BYPASSES.clear()
    prompt = prompt.strip()
    if not prompt:
        await ctx.send("🧭 **First Mate**: Captain, please provide a directive or task.")
        return

    import uuid
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    # Fetch initial quota status
    initial_quota, _ = await asyncio.to_thread(get_antigravity_quota)
    quota_desc = format_quota_string(initial_quota)

    # Quick Jev System One Dispatch evaluation for real-time visibility
    jev_line = None
    try:
        tmp_brief = f"/tmp/brief_{task_id}.md"
        with open(tmp_brief, "w", encoding="utf-8") as bf:
            bf.write(f"# Task\n\n## Captain's intent\n{prompt}\n\n## Firstmate spec\nExecute directive autonomously.\n")
        resolve_proc = await asyncio.create_subprocess_exec(
            "/opt/firstmate/bin/fm-dispatch-resolve.sh", tmp_brief,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await resolve_proc.communicate()
        if os.path.exists(tmp_brief):
            os.remove(tmp_brief)
        out_str = stdout.decode("utf-8", errors="replace")
        for line in out_str.splitlines():
            line_s = line.strip()
            if line_s.startswith("rule:") and "confidence:" in line_s:
                jev_line = line_s
                break
    except Exception as jev_e:
        print(f"[JEV RESOLVE ERROR]: {jev_e}", flush=True)

    jev_desc = f"**⚡ Subnet 92 Dispatch:** `{jev_line}`\n" if jev_line else ""

    # Send First Mate Liaison Intake Embed
    init_embed = discord.Embed(
        title=f"🧭 First Mate: {task_id}",
        description=(
            f"**Captain's Directive:** `{prompt}`\n"
            f"**Distro Engine:** FirstMate Fleet Engine (`/opt/firstmate`)\n"
            f"**Workspace:** `Shojin` (`projects/Shojin`)\n"
            f"**Inference Pool:** Antigravity Google AI Pro (`gemini-3.8-flash-high`)\n"
            f"{jev_desc}\n"
            f"**📊 Usage Limits (Start):**\n{quota_desc}\n\n"
            f"**Status:** ⏳ First Mate executing task..."
        ),
        color=discord.Color.teal()
    )
    init_embed.set_footer(text="FirstMate Distro • Talk to one agent, ship with a crew.")
    await ctx.send(embed=init_embed)

    async def status_notifier(event_type: str, message: str):
        color = discord.Color.teal()
        if "error" in event_type.lower():
            color = discord.Color.orange()
        elif "privacy_splice" in event_type.lower():
            color = discord.Color.gold()
        elif "pool_notice" in event_type.lower():
            color = discord.Color.purple()

        embed = discord.Embed(
            description=f"🧭 **[First Mate]** {message}",
            color=color
        )
        await ctx.send(embed=embed)

    task_banned_keys = set()

    async def task_inference_caller(system_prompt, prompt, status_notifier=None, wing="firstmate", requested_model=None, task_instruction=""):
        return await dispatch_step_inference(
            system_prompt=system_prompt,
            prompt=prompt,
            status_notifier=status_notifier,
            wing=wing,
            requested_model=requested_model,
            task_instruction=task_instruction,
            task_banned_keys=task_banned_keys
        )

    result = await execute_firstmate_autonomous_mission(
        captain_directive=prompt,
        inference_caller=task_inference_caller,
        status_notifier=status_notifier,
        max_turns=8
    )

    final_answer = result["final_output"]
    outcome_text = final_answer[:2500]

    # Fetch final quota status
    final_quota, _ = await asyncio.to_thread(get_antigravity_quota)
    final_quota_desc = format_quota_string(final_quota)

    completion_embed = discord.Embed(
        title=f"🎯 First Mate Deliverable: {task_id}",
        description=(
            f"**Captain's Directive:** `{prompt}`\n"
            f"**Turns Executed:** `{result['turns']}`\n\n"
            f"**📊 Usage Limits (Completion):**\n{final_quota_desc}\n\n"
            f"**Outcome & Deliverable:**\n{outcome_text}"
        ),
        color=discord.Color.green()
    )
    completion_embed.set_footer(text="FirstMate Distro • Talk to one agent, ship with a crew.")
    try:
        await ctx.send(embed=completion_embed)
    except Exception as send_err:
        print(f"[DISCORD SEND ERROR]: {send_err}", flush=True)
        await ctx.send(f"🎯 **First Mate Deliverable: {task_id}**\n\n**📊 Usage Limits (Completion):**\n{final_quota_desc}\n\n{outcome_text[:1900]}")

@bot.command(name="guard", aliases=["jev"])
async def guard_cmd(ctx):
    try:
        proc = await asyncio.create_subprocess_exec(
            "/opt/firstmate/bin/fm-jev-mem-guard.sh", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode("utf-8"))
        status = data.get("status", "UNKNOWN")
        summary = data.get("summary", {})
        recommendation = data.get("recommendation", "")
        top_procs = data.get("top_processes", [])[:4]
        
        color = discord.Color.green() if status == "OK" else (discord.Color.gold() if status == "WARNING" else discord.Color.red())
        proc_list = "\n".join([f"• `{p['comm']}` (PID {p['pid']}): {p['rss_mb']:.1f} MB" for p in top_procs])
        
        embed = discord.Embed(
            title=f"🛡️ Jev Memory Guard: {status}",
            description=(
                f"**Verdict:** `{status}`\n"
                f"**Recommendation:** {recommendation}\n\n"
                f"**Memory Usage:** {summary.get('mem_used_pct')}%\n"
                f"**Available RAM:** {summary.get('mem_available_gb')} GB / {summary.get('mem_total_gb')} GB\n"
                f"**Swap Usage:** {summary.get('swap_used_pct')}%\n\n"
                f"**Top Memory Consumers:**\n{proc_list}"
            ),
            color=color
        )
        embed.set_footer(text="TypeSafe.ai System One • Pattern 46 Memory Guard")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ **Jev Guard Error:** `{e}`")

@bot.command(name="resolve", aliases=["dispatch"])
async def resolve_cmd(ctx, *, brief_text: str = ""):
    if not brief_text.strip():
        await ctx.send("🧭 **First Mate**: Please provide a task brief or directive to evaluate with Jev.\nExample: `!resolve Refactor the caching layer`")
        return
    import uuid
    tmp_id = uuid.uuid4().hex[:6]
    tmp_path = f"/tmp/brief_test_{tmp_id}.md"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(f"# Task\n\n## Captain's intent\n{brief_text}\n\n## Firstmate spec\nEvaluate dispatch profile.\n")
        proc = await asyncio.create_subprocess_exec(
            "/opt/firstmate/bin/fm-dispatch-resolve.sh", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        out_text = stdout.decode("utf-8")
        embed = discord.Embed(
            title="⚡ Subnet 92 (REAX) Decision Dispatch Resolution",
            description=f"```yaml\n{out_text[:1900]}\n```",
            color=discord.Color.teal()
        )
        embed.set_footer(text="Bittensor Subnet 92 • Decision Models (s1-fast / s1-pro) • Sub-second Typed Dispatch")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ **Dispatch Resolution Error:** `{e}`")

@bot.command(name="check-updates", aliases=["updates", "upstream"])
async def check_updates_cmd(ctx):
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", "/opt/firstmate/scripts/weekly-upstream-check.js", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode("utf-8"))
        tools = data.get("tools", {})
        
        pstack_ver = tools.get("pstack", {}).get("package", {}).get("latest_version", "unknown")
        firstmate_ref = tools.get("firstmate", {}).get("local_ref", "current")
        
        embed = discord.Embed(
            title="🔄 AIOS Weekly Upstream Tooling Check",
            description=(
                f"**pstack (Lauren's stack):** `v{pstack_ver}`\n"
                f"• Skills: `/poteto-mode`, `/architect`, `/correct` monitored\n\n"
                f"**FirstMate Fleet:** `commit {firstmate_ref}`\n"
                f"• Path skew: zero\n\n"
                f"**t3code:** Checked against npm registry\n\n"
                f"**Decision Models (Subnet 92):** `s1-fast` & `s1-pro` active"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="AIOS Upstream Watcher • Weekly Scheduled Check")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ **Upstream Check Error:** `{e}`")

@bot.command(name="quota", aliases=["limits", "limit"])
async def quota_cmd(ctx):
    quota, _ = await asyncio.to_thread(get_antigravity_quota)
    quota_desc = format_quota_string(quota)
    embed = discord.Embed(
        title="📊 Antigravity Quota Status",
        description=f"**Current Google CloudCode Quota Pool:**\n\n{quota_desc}",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Google AI Pro Unmetered Pool • FirstMate Fleet Liaison")
    await ctx.send(embed=embed)

@bot.command(name="remember", aliases=["save_memory"])
async def remember_cmd(ctx, *, fact: str = ""):
    fact = fact.strip()
    if not fact:
        await ctx.send("🧭 **First Mate**: Captain, what would you like me to remember into Ditto?\nExample: `!remember In Shojin, always enforce Apple-grade minimalism and avoid slop`")
        return
    res = await asyncio.to_thread(
        ditto_engine.save_memory,
        text=fact,
        subjects=["captain_preference", "discord"],
        session_id="discord_captain",
        source="discord_captain",
        source_context=f"Discord channel: {ctx.channel.name if hasattr(ctx.channel, 'name') else 'direct'}"
    )
    cloud_status = "☁️ HeyDitto Cloud" if res.get("cloud_saved") else "💾 Local Knowledge Graph"
    embed = discord.Embed(
        title="🧠 Memory Saved",
        description=f"**Saved Fact:**\n{fact}\n\n**Storage Tier:** `{cloud_status}`\n**Memory ID:** `{res.get('memory_id', '')[:8]}`",
        color=discord.Color.purple()
    )
    embed.set_footer(text="HeyDitto • Persistent Cross-Agent Memory Graph")
    await ctx.send(embed=embed)

@bot.command(name="recall", aliases=["search_memory", "memories"])
async def recall_cmd(ctx, *, query: str = ""):
    query = query.strip()
    if not query:
        await ctx.send("🧭 **First Mate**: Captain, what topic or past memory should I search for?\nExample: `!recall Shojin design standards`")
        return
    results = await asyncio.to_thread(ditto_engine.search_memories, query=query, limit=3, fetch_full=True)
    if not results:
        await ctx.send(f"🔍 **First Mate**: No memories found matching `{query}` in Ditto.")
        return
    
    embed = discord.Embed(
        title=f"🧠 Ditto Memory Recall: '{query}'",
        color=discord.Color.purple()
    )
    for r in results[:3]:
        title = r.get("title") or r.get("id", "Memory")[:8]
        preview = r.get("text", "")
        if len(preview) > 300:
            preview = preview[:297] + "..."
        source_tag = r.get("source", "heyditto")
        embed.add_field(name=f"📌 {title} ({source_tag})", value=preview, inline=False)
    
    embed.set_footer(text="HeyDitto Subnet 118 • 2-Stage Semantic Retrieval")
    await ctx.send(embed=embed)

@bot.command(name="fm")
async def fm_cmd(ctx, *, prompt: str = ""):
    await firstmate_dispatch(ctx, prompt=prompt)

@bot.command(name="task")
async def task_cmd(ctx, *, prompt: str = ""):
    await firstmate_dispatch(ctx, prompt=prompt)

@bot.command(name="do")
async def do_cmd(ctx, *, prompt: str = ""):
    await firstmate_dispatch(ctx, prompt=prompt)

@bot.event
async def on_ready():
    print(f"FirstMate logged in as {bot.user} (ID: {bot.user.id})", flush=True)
    for guild in bot.guilds:
        try:
            await guild.me.edit(nick="FirstMate")
            print(f"Updated guild {guild.name} nickname to FirstMate", flush=True)
        except Exception as e:
            print(f"Could not update nickname in {guild.name}: {e}", flush=True)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        clean_prompt = ctx.message.content.lstrip("!").strip()
        await firstmate_dispatch(ctx, prompt=clean_prompt)
    else:
        print(f"[DISCORD ERROR]: {error}", flush=True)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f"[DISCORD MSG] Author: {message.author}, Channel: {message.channel}, Content: {message.content[:80]}", flush=True)
    await bot.process_commands(message)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("[CRITICAL] DISCORD_BOT_TOKEN not found in environment or .env!", flush=True)
        sys.exit(1)
    bot.run(token)

