-- H2 development schema (compatible with MySQL mode)

CREATE TABLE IF NOT EXISTS work_mode (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    mode_id VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    icon VARCHAR(32) DEFAULT '',
    theme_config TEXT,
    agent_config TEXT,
    system_prompt TEXT,
    tools_config TEXT,
    sort_order INT DEFAULT 0,
    is_builtin TINYINT DEFAULT 0,
    deleted TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_session (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL UNIQUE,
    mode_id VARCHAR(64) NOT NULL DEFAULT 'general',
    title VARCHAR(256) DEFAULT '',
    deleted TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_message (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT,
    token_count INT DEFAULT 0,
    model VARCHAR(128) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag_trace_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) DEFAULT '',
    mode_id VARCHAR(64) DEFAULT 'general',
    original_query TEXT,
    rewritten_query TEXT,
    retrieval_method VARCHAR(64) DEFAULT '',
    retrieved_count INT DEFAULT 0,
    after_rerank_count INT DEFAULT 0,
    total_latency_ms DOUBLE DEFAULT 0,
    quality_metrics TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_execution_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    execution_id VARCHAR(64) NOT NULL UNIQUE,
    session_id VARCHAR(64) DEFAULT '',
    mode_id VARCHAR(64) DEFAULT 'general',
    strategy VARCHAR(32) DEFAULT 'react',
    total_steps INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    total_latency_ms DOUBLE DEFAULT 0,
    status VARCHAR(16) DEFAULT 'running',
    error_message TEXT,
    steps_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- Default work modes
INSERT INTO work_mode (mode_id, name, description, icon, is_builtin, sort_order) VALUES
('general', 'General Assistant', 'Default general-purpose AI assistant', 'S', 1, 0),
('code', 'Code Workshop', 'Software development focused mode', 'C', 1, 1),
('research', 'Deep Research', 'Academic and technical research mode', 'R', 1, 2),
('writing', 'Creative Writing', 'Content creation and editing mode', 'W', 1, 3);
