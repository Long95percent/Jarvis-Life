import os
import json
import urllib.request
import urllib.error

LLM_CONFIG_FILE = "llm_config.json"

def _read_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return default
    return default

def _write_json(path: str, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def _default_llm_config():
    return {
        "active_agent_id": "openai_compatible",
        "agents": [
            {
                "id": "openai_compatible",
                "name": "OpenAI-Compatible API",
                "type": "api",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o-mini",
            },
            {
                "id": "local_model",
                "name": "Local Model",
                "type": "local",
                "base_url": "http://127.0.0.1:8000/v1",
                "model": "local-model",
                "folder_path": "",
            },
        ],
        "secrets": {
            "openai_compatible": {"api_key": ""},
        },
    }

def normalize_llm_config(cfg):
    if not isinstance(cfg, dict):
        cfg = {}
    if not isinstance(cfg.get("agents"), list):
        cfg["agents"] = []
    if not isinstance(cfg.get("secrets"), dict):
        cfg["secrets"] = {}
    if not isinstance(cfg.get("skills"), list):
        cfg["skills"] = []
    if not isinstance(cfg.get("agent_permissions"), dict):
        cfg["agent_permissions"] = {}

    existing_ids = set()
    normalized_agents = []
    for a in cfg.get("agents", []):
        if not isinstance(a, dict):
            continue
        agent_id = (a.get("id") or "").strip()
        if not agent_id or agent_id in existing_ids:
            continue
        existing_ids.add(agent_id)
        agent_type = (a.get("type") or "").strip() or "api"
        normalized_agents.append(
            {
                "id": agent_id,
                "name": (a.get("name") or agent_id).strip(),
                "type": agent_type,
                "base_url": (a.get("base_url") or "").strip(),
                "model": (a.get("model") or "").strip(),
                "folder_path": (a.get("folder_path") or "").strip() if agent_type == "local" else "",
                "engine": (a.get("engine") or "auto").strip() if agent_type == "local" else "auto",
                "extra_body": a.get("extra_body") if agent_type == "api" and isinstance(a.get("extra_body"), dict) else {},
                "stream_options": a.get("stream_options") if agent_type == "api" and isinstance(a.get("stream_options"), dict) else {},
            }
        )

    if not normalized_agents:
        cfg = _default_llm_config()
        normalized_agents = cfg["agents"]

    cfg["agents"] = normalized_agents

    active_agent_id = (cfg.get("active_agent_id") or "").strip()
    if not active_agent_id or active_agent_id not in {a["id"] for a in cfg["agents"]}:
        cfg["active_agent_id"] = cfg["agents"][0]["id"]

    for a in cfg["agents"]:
        if a["type"] == "api":
            cfg["secrets"].setdefault(a["id"], {})
            if "api_key" not in cfg["secrets"][a["id"]]:
                cfg["secrets"][a["id"]]["api_key"] = ""

    return cfg

def load_llm_config():
    cfg = _read_json(LLM_CONFIG_FILE, _default_llm_config())
    cfg = normalize_llm_config(cfg)
    if not os.path.exists(LLM_CONFIG_FILE):
        _write_json(LLM_CONFIG_FILE, cfg)
    return cfg

def save_llm_config(cfg) -> bool:
    cfg = normalize_llm_config(cfg)
    return _write_json(LLM_CONFIG_FILE, cfg)

def get_agent(cfg, agent_id: str):
    for a in cfg.get("agents", []):
        if a.get("id") == agent_id:
            return a
    return None

def is_ollama_endpoint(url: str) -> bool:
    u = (url or "").lower()
    return "/api/chat" in u or "/api/generate" in u

def _http_json_post_stream(url: str, headers: dict, payload: dict, timeout_s: int = 60):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        if v is None:
            continue
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        for line in resp:
            if line:
                yield line.decode("utf-8", errors="replace")

def chat_openai_compatible_stream(base_url: str, api_key: str | None, model: str, messages: list[dict], extra_body: dict | None = None, stream_options: dict | None = None):
    base = (base_url or "").rstrip("/")
    if not base:
        raise RuntimeError("Base URL is empty.")
    if base.lower().endswith("/chat/completions"):
        url = base
    else:
        url = f"{base}/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.7,
        "stream": True
    }
    if extra_body:
        payload["extra_body"] = extra_body
    if stream_options:
        payload["stream_options"] = stream_options
    
    for line in _http_json_post_stream(url, headers, payload):
        line = line.strip()
        if not line:
            continue
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
            except json.JSONDecodeError:
                pass

def chat_ollama_stream(base_url: str, model: str, messages: list[dict]):
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise RuntimeError("Base URL is empty.")

    # Convert /v1 to base URL for ollama API
    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")

    if "/api/generate" in url.lower():
        api_url = url
    elif "/api/chat" in url.lower():
        api_url = url
    else:
        api_url = f"{url}/api/chat"

    if "/api/generate" in api_url.lower():
        prompt_parts = []
        for m in messages or []:
            role = (m.get("role") or "").strip()
            content = (m.get("content") or "").strip()
            if not content:
                continue
            prompt_parts.append(f"{role}: {content}")
        prompt = "\n".join(prompt_parts).strip()
        
        payload = {"model": model or "llama3.2", "prompt": prompt, "stream": True}
        for line in _http_json_post_stream(api_url, {}, payload):
            try:
                data = json.loads(line)
                resp = data.get("response", "")
                if resp:
                    yield resp
            except json.JSONDecodeError:
                pass
    else:
        payload = {"model": model or "llama3.2", "messages": messages, "stream": True}
        for line in _http_json_post_stream(api_url, {}, payload):
            try:
                data = json.loads(line)
                msg = (data.get("message") or {}).get("content", "")
                if msg:
                    yield msg
            except json.JSONDecodeError:
                pass
