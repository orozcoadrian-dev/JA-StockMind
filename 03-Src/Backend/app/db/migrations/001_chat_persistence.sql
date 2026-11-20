CREATE TABLE IF NOT EXISTS chat_sessions (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    external_id VARCHAR(36) NOT NULL,
    title VARCHAR(80) NULL,
    status ENUM('active', 'archived') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_message_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    message_count INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_chat_sessions_external_id (external_id),
    KEY idx_chat_sessions_last_message (last_message_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id INT UNSIGNED NOT NULL,
    seq INT UNSIGNED NOT NULL,
    `role` ENUM('user', 'assistant', 'tool', 'system') NOT NULL,
    content LONGTEXT NOT NULL,
    tool_name VARCHAR(60) NULL,
    tool_call_id VARCHAR(100) NULL,
    tool_calls JSON NULL,
    tool_result JSON NULL,
    agent_action_id INT UNSIGNED NULL,
    model VARCHAR(100) NULL,
    tokens_input INT UNSIGNED NULL,
    tokens_output INT UNSIGNED NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_chat_messages_session_seq (session_id, seq),
    KEY idx_chat_messages_session (session_id),
    KEY idx_chat_messages_session_created (session_id, created_at),
    CONSTRAINT fk_chat_messages_session
        FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_chat_messages_agent_action
        FOREIGN KEY (agent_action_id) REFERENCES agent_actions (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @chat_action_column_exists = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'agent_actions'
      AND column_name = 'chat_session_id'
);
SET @chat_action_column_sql = IF(
    @chat_action_column_exists = 0,
    'ALTER TABLE agent_actions ADD COLUMN chat_session_id INT UNSIGNED NULL',
    'SELECT 1'
);
PREPARE chat_action_column_stmt FROM @chat_action_column_sql;
EXECUTE chat_action_column_stmt;
DEALLOCATE PREPARE chat_action_column_stmt;

SET @chat_action_index_exists = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'agent_actions'
      AND index_name = 'idx_actions_chat_session'
);
SET @chat_action_index_sql = IF(
    @chat_action_index_exists = 0,
    'CREATE INDEX idx_actions_chat_session ON agent_actions (chat_session_id)',
    'SELECT 1'
);
PREPARE chat_action_index_stmt FROM @chat_action_index_sql;
EXECUTE chat_action_index_stmt;
DEALLOCATE PREPARE chat_action_index_stmt;

SET @chat_action_fk_exists = (
    SELECT COUNT(*)
    FROM information_schema.table_constraints
    WHERE constraint_schema = DATABASE()
      AND table_name = 'agent_actions'
      AND constraint_name = 'fk_agent_actions_chat_session'
      AND constraint_type = 'FOREIGN KEY'
);
SET @chat_action_fk_sql = IF(
    @chat_action_fk_exists = 0,
    'ALTER TABLE agent_actions ADD CONSTRAINT fk_agent_actions_chat_session FOREIGN KEY (chat_session_id) REFERENCES chat_sessions (id) ON DELETE RESTRICT',
    'SELECT 1'
);
PREPARE chat_action_fk_stmt FROM @chat_action_fk_sql;
EXECUTE chat_action_fk_stmt;
DEALLOCATE PREPARE chat_action_fk_stmt;
