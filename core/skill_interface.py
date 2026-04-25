import importlib
import inspect


def import_from_string(ref: str):
    r = (ref or "").strip()
    if not r:
        raise ValueError("Empty import ref")
    if ":" in r:
        module_path, attr_path = r.split(":", 1)
    else:
        module_path, attr_path = r, ""
    module_path = module_path.strip()
    attr_path = (attr_path or "").strip()
    module = importlib.import_module(module_path)
    if not attr_path:
        return module
    obj = module
    for part in attr_path.split("."):
        part = part.strip()
        if not part:
            continue
        obj = getattr(obj, part)
    return obj


def _call_with_context(fn, context: dict, kwargs: dict):
    ctx = context if isinstance(context, dict) else {}
    kw = dict(kwargs) if isinstance(kwargs, dict) else {}

    try:
        sig = inspect.signature(fn)
        for name, p in sig.parameters.items():
            if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if name in ctx and name not in kw:
                kw[name] = ctx[name]
        return fn(**kw)
    except TypeError:
        pass

    if kw:
        try:
            return fn(**kw)
        except TypeError:
            pass
    try:
        return fn(ctx)
    except TypeError:
        return fn()


def _coerce_tools(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, dict):
        tools = obj.get("tools")
        if isinstance(tools, list):
            return tools
        return []
    get_tools = getattr(obj, "get_tools", None)
    if callable(get_tools):
        return _coerce_tools(get_tools())
    return []


def load_skill_tools(skills_config, context: dict):
    skills = skills_config if isinstance(skills_config, list) else []
    out = []
    ctx = context if isinstance(context, dict) else {}

    for item in skills:
        if isinstance(item, str):
            spec = {"ref": item, "enabled": True, "kwargs": {}}
        elif isinstance(item, dict):
            spec = dict(item)
        else:
            continue

        if not bool(spec.get("enabled", True)):
            continue

        ref = (spec.get("ref") or "").strip()
        if not ref:
            continue

        kwargs = spec.get("kwargs") if isinstance(spec.get("kwargs"), dict) else {}
        name_prefix = (spec.get("name_prefix") or "").strip()

        try:
            target = import_from_string(ref)
            produced = None
            if inspect.isclass(target):
                inst = _call_with_context(target, ctx, kwargs)
                produced = inst
            elif callable(target):
                produced = _call_with_context(target, ctx, kwargs)
            else:
                produced = target
            tools = _coerce_tools(produced)
        except Exception:
            continue

        for t in tools:
            if not t:
                continue
            if name_prefix:
                try:
                    t.name = f"{name_prefix}{getattr(t, 'name', '')}"
                except Exception:
                    pass
            out.append(t)

    return out


def load_skill_tools_with_report(skills_config, context: dict):
    skills = skills_config if isinstance(skills_config, list) else []
    ctx = context if isinstance(context, dict) else {}
    out = []
    report = {"loaded": [], "errors": []}

    for item in skills:
        if isinstance(item, str):
            spec = {"ref": item, "enabled": True, "kwargs": {}}
        elif isinstance(item, dict):
            spec = dict(item)
        else:
            continue

        if not bool(spec.get("enabled", True)):
            continue

        ref = (spec.get("ref") or "").strip()
        if not ref:
            continue

        kwargs = spec.get("kwargs") if isinstance(spec.get("kwargs"), dict) else {}
        name_prefix = (spec.get("name_prefix") or "").strip()

        try:
            target = import_from_string(ref)
            if inspect.isclass(target):
                produced = _call_with_context(target, ctx, kwargs)
            elif callable(target):
                produced = _call_with_context(target, ctx, kwargs)
            else:
                produced = target
            tools = _coerce_tools(produced)
            for t in tools:
                if not t:
                    continue
                if name_prefix:
                    try:
                        t.name = f"{name_prefix}{getattr(t, 'name', '')}"
                    except Exception:
                        pass
                out.append(t)
            report["loaded"].append({"ref": ref, "count": len(tools), "tools": [getattr(t, "name", "") for t in tools]})
        except Exception as e:
            report["errors"].append({"ref": ref, "error": str(e)})

    return out, report
