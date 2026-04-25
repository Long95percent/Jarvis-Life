def register(llm_cfg, mode_id):
    from langchain_community.tools import DuckDuckGoSearchRun
    return [DuckDuckGoSearchRun(name="ddg_search_ext")]