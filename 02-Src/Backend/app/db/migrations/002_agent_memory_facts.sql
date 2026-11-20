CREATE TABLE IF NOT EXISTS agent_memory_facts (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `key` VARCHAR(120) NOT NULL,
    `value` TEXT NOT NULL,
    source_session_id INT UNSIGNED NOT NULL,
    source_message_id INT UNSIGNED NULL,
    status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_agent_memory_facts_status_updated (status, updated_at),
    KEY idx_agent_memory_facts_source_session (source_session_id),
    KEY idx_agent_memory_facts_source_message (source_message_id),
    CONSTRAINT fk_agent_memory_facts_session
        FOREIGN KEY (source_session_id) REFERENCES chat_sessions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_agent_memory_facts_message
        FOREIGN KEY (source_message_id) REFERENCES chat_messages (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
