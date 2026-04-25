-- ============================================================
-- ShadowLink Database Initialization
-- Runs on first MySQL container start
-- ============================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET time_zone = '+08:00';

-- ── Schema Version Tracking ──
CREATE TABLE IF NOT EXISTS `schema_version` (
    `version` VARCHAR(32) NOT NULL PRIMARY KEY,
    `description` VARCHAR(256) NOT NULL,
    `applied_at` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `schema_version` (`version`, `description`) VALUES ('0.1.0', 'Initial schema creation');

-- ════════════════════════════════════════════
-- User & Auth
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `user_id` VARCHAR(64) NOT NULL UNIQUE COMMENT 'Public user identifier (UUID)',
    `username` VARCHAR(128) NOT NULL UNIQUE,
    `password_hash` VARCHAR(256) NOT NULL,
    `nickname` VARCHAR(128) DEFAULT '',
    `email` VARCHAR(256) DEFAULT '',
    `avatar_url` VARCHAR(512) DEFAULT '',
    `role` VARCHAR(32) DEFAULT 'user' COMMENT 'admin | user | guest',
    `status` TINYINT DEFAULT 1 COMMENT '1=active, 0=disabled',
    `last_login_at` DATETIME,
    `deleted` TINYINT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_username` (`username`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default admin user (password: admin123 — BCrypt hash)
INSERT INTO `user` (`user_id`, `username`, `password_hash`, `nickname`, `role`) VALUES
('00000000-0000-0000-0000-000000000001', 'admin', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'Administrator', 'admin');

-- ════════════════════════════════════════════
-- Work Modes
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `work_mode` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `mode_id` VARCHAR(64) NOT NULL UNIQUE COMMENT 'Unique mode identifier',
    `name` VARCHAR(128) NOT NULL COMMENT 'Display name',
    `description` TEXT COMMENT 'Mode description',
    `icon` VARCHAR(32) DEFAULT '' COMMENT 'Lucide icon name',
    `theme_config` JSON COMMENT 'AmbientTheme JSON overrides',
    `agent_config` JSON COMMENT 'Agent strategy & parameter overrides',
    `system_prompt` TEXT COMMENT 'Mode-specific system prompt',
    `tools_config` JSON COMMENT 'Enabled tools whitelist',
    `rag_config` JSON COMMENT 'RAG pipeline overrides per mode',
    `sort_order` INT DEFAULT 0,
    `is_builtin` TINYINT DEFAULT 0 COMMENT '1=system preset, 0=user-created',
    `created_by` BIGINT DEFAULT NULL,
    `deleted` TINYINT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_sort` (`sort_order`),
    INDEX `idx_builtin` (`is_builtin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default work modes (matching frontend presets)
INSERT INTO `work_mode` (`mode_id`, `name`, `description`, `icon`, `is_builtin`, `sort_order`, `system_prompt`) VALUES
('general',            'General Assistant',     'Balanced workspace for everyday AI interactions',                  'MessageSquare',  1, 0, 'You are ShadowLink, a versatile AI assistant. Respond helpfully, accurately, and concisely.'),
('code-dev',           'Code & Development',    'Optimized for coding, debugging, and technical tasks',             'Code2',          1, 1, 'You are ShadowLink in Code mode. Focus on writing correct, efficient, well-structured code. Explain technical concepts precisely. Use code blocks with language tags.'),
('paper-reading',      'Paper & Reading',       'Comfortable reading mode for papers, docs, and research',          'BookOpen',       1, 2, 'You are ShadowLink in Research mode. Help the user analyze academic papers, extract key insights, identify methodologies, and summarize findings. Be thorough and cite specific sections.'),
('creative-writing',   'Creative Writing',      'Inspiring workspace for writing, brainstorming, and storytelling', 'Pen',            1, 3, 'You are ShadowLink in Creative mode. Help with writing, brainstorming, and storytelling. Be imaginative, expressive, and stylistically aware. Offer constructive feedback on prose.'),
('data-analysis',      'Data Analysis',         'Precision workspace for data exploration and visualization',       'BarChart3',      1, 4, 'You are ShadowLink in Data Analysis mode. Help analyze datasets, write SQL/Python for data processing, suggest visualizations, and interpret statistical results with precision.'),
('project-management', 'Project Management',    'Organized workspace for planning, tracking, and collaboration',    'KanbanSquare',   1, 5, 'You are ShadowLink in Project mode. Help plan tasks, track progress, draft documents, and organize workflows. Be structured, action-oriented, and deadline-aware.');

-- ════════════════════════════════════════════
-- Chat Sessions & Messages
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `chat_session` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `session_id` VARCHAR(64) NOT NULL UNIQUE,
    `user_id` VARCHAR(64) NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    `mode_id` VARCHAR(64) NOT NULL DEFAULT 'general',
    `title` VARCHAR(256) DEFAULT '',
    `message_count` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `pinned` TINYINT DEFAULT 0,
    `archived` TINYINT DEFAULT 0,
    `deleted` TINYINT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_user_mode` (`user_id`, `mode_id`),
    INDEX `idx_updated` (`updated_at` DESC),
    INDEX `idx_pinned` (`pinned`, `updated_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `chat_message` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `message_id` VARCHAR(64) NOT NULL UNIQUE COMMENT 'UUID for client reference',
    `session_id` VARCHAR(64) NOT NULL,
    `role` VARCHAR(16) NOT NULL COMMENT 'user | assistant | system | tool',
    `content` MEDIUMTEXT,
    `token_count` INT DEFAULT 0,
    `model` VARCHAR(128) DEFAULT '',
    `metadata` JSON COMMENT 'Extra: tool_calls, rag_context_ids, etc.',
    `deleted` TINYINT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_session_created` (`session_id`, `created_at`),
    INDEX `idx_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ════════════════════════════════════════════
-- Knowledge Base (RAG)
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `knowledge_document` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `doc_id` VARCHAR(64) NOT NULL UNIQUE,
    `user_id` VARCHAR(64) NOT NULL,
    `mode_id` VARCHAR(64) DEFAULT 'general' COMMENT 'Mode-partitioned index',
    `file_name` VARCHAR(512) NOT NULL,
    `file_type` VARCHAR(32) NOT NULL COMMENT 'pdf | docx | md | txt | ...',
    `file_size` BIGINT DEFAULT 0 COMMENT 'Bytes',
    `file_path` VARCHAR(1024) DEFAULT '' COMMENT 'Storage path',
    `chunk_count` INT DEFAULT 0,
    `chunking_strategy` VARCHAR(64) DEFAULT 'recursive',
    `embedding_model` VARCHAR(128) DEFAULT '',
    `status` VARCHAR(32) DEFAULT 'pending' COMMENT 'pending | processing | indexed | failed',
    `error_message` TEXT,
    `deleted` TINYINT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_user_mode` (`user_id`, `mode_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_file_type` (`file_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ════════════════════════════════════════════
-- Agent Execution Logs
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `agent_execution_log` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `execution_id` VARCHAR(64) NOT NULL UNIQUE,
    `session_id` VARCHAR(64) DEFAULT '',
    `user_id` VARCHAR(64) DEFAULT '',
    `mode_id` VARCHAR(64) DEFAULT 'general',
    `strategy` VARCHAR(32) DEFAULT 'react' COMMENT 'direct | react | plan_execute | supervisor | hierarchical | swarm | hermes',
    `input_message` TEXT COMMENT 'Original user input',
    `output_message` TEXT COMMENT 'Final agent response',
    `total_steps` INT DEFAULT 0,
    `total_tokens` INT DEFAULT 0,
    `total_latency_ms` DOUBLE DEFAULT 0,
    `status` VARCHAR(16) DEFAULT 'running' COMMENT 'running | success | failed | cancelled | timeout',
    `error_message` TEXT,
    `steps_json` JSON COMMENT 'Array of {stepType, toolName, latencyMs, tokenCount}',
    `plan_json` JSON COMMENT 'Plan steps for plan_execute strategy',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `finished_at` DATETIME,
    INDEX `idx_session` (`session_id`),
    INDEX `idx_user_mode` (`user_id`, `mode_id`),
    INDEX `idx_strategy` (`strategy`),
    INDEX `idx_status_created` (`status`, `created_at` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ════════════════════════════════════════════
-- RAG Trace Logs (observability)
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `rag_trace_log` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `trace_id` VARCHAR(64) NOT NULL UNIQUE,
    `session_id` VARCHAR(64) DEFAULT '',
    `user_id` VARCHAR(64) DEFAULT '',
    `mode_id` VARCHAR(64) DEFAULT 'general',
    `original_query` TEXT,
    `rewritten_query` TEXT,
    `query_classification` VARCHAR(64) DEFAULT '' COMMENT 'factual | analytical | creative | code',
    `retrieval_method` VARCHAR(64) DEFAULT '' COMMENT 'dense | sparse | hybrid',
    `retrieved_count` INT DEFAULT 0,
    `after_rerank_count` INT DEFAULT 0,
    `quality_gate_passed` TINYINT DEFAULT 1 COMMENT 'CRAG quality gate result',
    `total_latency_ms` DOUBLE DEFAULT 0,
    `quality_metrics` JSON COMMENT '{"recall":0.8, "precision":0.7, "relevance_avg":0.9}',
    `chunk_ids` JSON COMMENT 'Array of retrieved chunk IDs',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_session` (`session_id`),
    INDEX `idx_mode_created` (`mode_id`, `created_at` DESC),
    INDEX `idx_classification` (`query_classification`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ════════════════════════════════════════════
-- Plugin Registry
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `plugin_registry` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `plugin_id` VARCHAR(64) NOT NULL UNIQUE,
    `name` VARCHAR(128) NOT NULL,
    `description` TEXT,
    `version` VARCHAR(32) DEFAULT '0.1.0',
    `author` VARCHAR(128) DEFAULT '',
    `category` VARCHAR(64) DEFAULT 'general' COMMENT 'general | tool | mcp | retriever',
    `entry_point` VARCHAR(256) NOT NULL COMMENT 'Python module path or MCP server URI',
    `config_schema` JSON COMMENT 'JSON Schema for plugin configuration',
    `default_config` JSON,
    `enabled` TINYINT DEFAULT 1,
    `allowed_modes` JSON COMMENT 'Array of mode_ids; null = all modes',
    `deleted` TINYINT DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_category` (`category`),
    INDEX `idx_enabled` (`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ════════════════════════════════════════════
-- System Settings (key-value)
-- ════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS `system_setting` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `setting_key` VARCHAR(128) NOT NULL UNIQUE,
    `setting_value` TEXT,
    `value_type` VARCHAR(16) DEFAULT 'string' COMMENT 'string | number | boolean | json',
    `description` VARCHAR(256) DEFAULT '',
    `updated_by` VARCHAR(64) DEFAULT '',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default system settings
INSERT INTO `system_setting` (`setting_key`, `setting_value`, `value_type`, `description`) VALUES
('llm.base_url',   'http://localhost:11434/v1', 'string',  'LLM API base URL'),
('llm.model',      'gpt-4o-mini',              'string',  'Default LLM model'),
('llm.temperature','0.7',                       'number',  'LLM temperature'),
('llm.max_tokens', '4096',                      'number',  'LLM max tokens per request'),
('app.language',   'zh-CN',                     'string',  'UI language'),
('app.version',    '3.0.0',                     'string',  'Application version');
