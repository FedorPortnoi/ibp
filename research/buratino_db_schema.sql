-- ИАС Буратино - Reconstructed Database Schema
-- This is a reverse-engineered schema based on feature analysis
-- Not official documentation

-- ============================================
-- CORE TABLES
-- ============================================

-- Users of the Buratino system (subscribers)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    organization VARCHAR(255),
    phone VARCHAR(50),
    subscription_expires DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Investigation cases/projects
CREATE TABLE investigations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    target_name VARCHAR(255),
    target_vk_id BIGINT,
    status VARCHAR(50) DEFAULT 'active', -- active, archived, completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- VK PROFILE DATA
-- ============================================

-- Cached VK profiles (to avoid repeated API calls)
CREATE TABLE vk_profiles (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT UNIQUE NOT NULL,

    -- Basic info
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    maiden_name VARCHAR(255),
    screen_name VARCHAR(255),
    bdate VARCHAR(50),
    sex SMALLINT,

    -- Location
    city_id INTEGER,
    city_name VARCHAR(255),
    country_id INTEGER,
    country_name VARCHAR(255),

    -- Photos
    photo_50 TEXT,
    photo_100 TEXT,
    photo_200 TEXT,
    photo_max_orig TEXT,

    -- Status
    status TEXT,
    last_seen_time INTEGER,
    last_seen_platform INTEGER,
    online BOOLEAN,

    -- Counts
    friends_count INTEGER,
    followers_count INTEGER,

    -- Raw JSON for full data
    raw_data JSONB,

    -- Metadata
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Index for faster lookups
    INDEX idx_vk_profiles_name (first_name, last_name),
    INDEX idx_vk_profiles_city (city_name)
);

-- Education history
CREATE TABLE vk_education (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT REFERENCES vk_profiles(vk_id) ON DELETE CASCADE,
    university_id INTEGER,
    university_name VARCHAR(255),
    faculty_id INTEGER,
    faculty_name VARCHAR(255),
    graduation INTEGER,
    education_form VARCHAR(50),
    education_status VARCHAR(50)
);

-- Career/work history
CREATE TABLE vk_career (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT REFERENCES vk_profiles(vk_id) ON DELETE CASCADE,
    company VARCHAR(255),
    group_id BIGINT,
    country_id INTEGER,
    city_id INTEGER,
    city_name VARCHAR(255),
    position VARCHAR(255),
    from_year INTEGER,
    until_year INTEGER
);

-- Contact information
CREATE TABLE vk_contacts (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT REFERENCES vk_profiles(vk_id) ON DELETE CASCADE,
    mobile_phone VARCHAR(100),
    home_phone VARCHAR(100),
    site TEXT,
    skype VARCHAR(100),
    twitter VARCHAR(100),
    instagram VARCHAR(100),
    facebook VARCHAR(255)
);

-- ============================================
-- SOCIAL GRAPH DATA
-- ============================================

-- Friends relationships
CREATE TABLE vk_friends (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    friend_vk_id BIGINT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(vk_id, friend_vk_id),
    INDEX idx_friends_vk_id (vk_id),
    INDEX idx_friends_friend_id (friend_vk_id)
);

-- Mutual friends cache
CREATE TABLE vk_mutual_friends (
    id SERIAL PRIMARY KEY,
    source_vk_id BIGINT NOT NULL,
    target_vk_id BIGINT NOT NULL,
    mutual_count INTEGER,
    mutual_ids JSONB, -- Array of mutual friend VK IDs
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source_vk_id, target_vk_id)
);

-- Group memberships
CREATE TABLE vk_groups (
    id SERIAL PRIMARY KEY,
    group_id BIGINT UNIQUE NOT NULL,
    name VARCHAR(255),
    screen_name VARCHAR(255),
    type VARCHAR(50), -- group, page, event
    is_closed BOOLEAN,
    members_count INTEGER,
    photo_url TEXT,
    description TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE vk_user_groups (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    group_id BIGINT REFERENCES vk_groups(group_id) ON DELETE CASCADE,
    is_admin BOOLEAN DEFAULT FALSE,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(vk_id, group_id),
    INDEX idx_user_groups_vk_id (vk_id)
);

-- ============================================
-- WALL POSTS & CONTENT
-- ============================================

-- Wall posts
CREATE TABLE vk_wall_posts (
    id SERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL, -- vk_id of the wall owner
    from_id BIGINT, -- who posted (can be different if posted by friend)

    post_date TIMESTAMP,
    text TEXT,

    -- Engagement metrics
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    reposts_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,

    -- Post type and content
    post_type VARCHAR(50), -- post, copy, reply, postpone, suggest
    is_pinned BOOLEAN DEFAULT FALSE,

    -- Attachments stored as JSON
    attachments JSONB,

    -- Copy history for reposts
    copy_history JSONB,

    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(post_id, owner_id),
    INDEX idx_wall_posts_owner (owner_id),
    INDEX idx_wall_posts_date (post_date)
);

-- Photos
CREATE TABLE vk_photos (
    id SERIAL PRIMARY KEY,
    photo_id BIGINT NOT NULL,
    owner_id BIGINT NOT NULL,
    album_id BIGINT,

    url_75 TEXT,
    url_130 TEXT,
    url_604 TEXT,
    url_807 TEXT,
    url_1280 TEXT,
    url_2560 TEXT,

    width INTEGER,
    height INTEGER,
    text TEXT,

    photo_date TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(photo_id, owner_id),
    INDEX idx_photos_owner (owner_id)
);

-- ============================================
-- ANALYSIS RESULTS
-- ============================================

-- Analysis task tracking
CREATE TABLE analysis_tasks (
    id SERIAL PRIMARY KEY,
    investigation_id INTEGER REFERENCES investigations(id) ON DELETE SET NULL,
    vk_id BIGINT NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,

    status VARCHAR(50) DEFAULT 'queued', -- queued, running, completed, failed
    progress DECIMAL(5,2) DEFAULT 0,
    current_stage VARCHAR(100),

    include_friends BOOLEAN DEFAULT TRUE,
    include_text_analysis BOOLEAN DEFAULT TRUE,
    include_graph BOOLEAN DEFAULT TRUE,
    custom_dictionary_id INTEGER,

    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk analysis results
CREATE TABLE analysis_risk_scores (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    analysis_task_id INTEGER REFERENCES analysis_tasks(id) ON DELETE CASCADE,

    overall_score DECIMAL(5,2),
    extremism_score DECIMAL(5,2),
    violence_score DECIMAL(5,2),
    substance_abuse_score DECIMAL(5,2),
    gambling_score DECIMAL(5,2),
    financial_risk_score DECIMAL(5,2),
    criminal_association_score DECIMAL(5,2),

    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_risk_scores_vk_id (vk_id)
);

-- Activity metrics results
CREATE TABLE analysis_activity_metrics (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    analysis_task_id INTEGER REFERENCES analysis_tasks(id) ON DELETE CASCADE,

    openness_score DECIMAL(5,2),
    activity_level DECIMAL(5,2),
    chattiness_score DECIMAL(5,2),
    engagement_rate DECIMAL(5,2),

    posts_per_month DECIMAL(10,2),
    avg_post_length DECIMAL(10,2),
    total_posts_analyzed INTEGER,

    peak_activity_hours JSONB, -- Array of most active hours
    content_type_breakdown JSONB, -- {text: %, photo: %, repost: %}

    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_activity_metrics_vk_id (vk_id)
);

-- Text analysis / sentiment results
CREATE TABLE analysis_text_results (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    analysis_task_id INTEGER REFERENCES analysis_tasks(id) ON DELETE CASCADE,

    sentiment_positive DECIMAL(5,4),
    sentiment_negative DECIMAL(5,4),
    sentiment_neutral DECIMAL(5,4),
    sentiment_overall VARCHAR(20), -- positive, negative, neutral, mixed

    topics_detected JSONB, -- Array of detected topics
    flagged_posts JSONB, -- Posts that triggered risk categories

    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_text_results_vk_id (vk_id)
);

-- Dictionary match results
CREATE TABLE analysis_dictionary_matches (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    analysis_task_id INTEGER REFERENCES analysis_tasks(id) ON DELETE CASCADE,
    dictionary_id INTEGER,

    word VARCHAR(255),
    match_count INTEGER,
    matched_post_ids JSONB, -- Array of post IDs containing the word

    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- SOCIAL GRAPH SNAPSHOTS
-- ============================================

-- Pre-computed graph data for visualization
CREATE TABLE graph_snapshots (
    id SERIAL PRIMARY KEY,
    vk_id BIGINT NOT NULL,
    analysis_task_id INTEGER REFERENCES analysis_tasks(id) ON DELETE CASCADE,

    depth INTEGER DEFAULT 1,
    nodes_count INTEGER,
    edges_count INTEGER,

    -- Full graph data as JSON for vis.js
    graph_data JSONB, -- {nodes: [...], edges: [...]}

    -- Detected clusters
    clusters JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_graph_snapshots_vk_id (vk_id)
);

-- ============================================
-- USER FEATURES
-- ============================================

-- Custom dictionaries for text analysis
CREATE TABLE custom_dictionaries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    words JSONB NOT NULL, -- Array of words/phrases
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Monitoring subscriptions
CREATE TABLE monitoring_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    vk_id BIGINT NOT NULL,
    investigation_id INTEGER REFERENCES investigations(id) ON DELETE SET NULL,

    monitor_posts BOOLEAN DEFAULT TRUE,
    monitor_friends BOOLEAN DEFAULT TRUE,
    monitor_groups BOOLEAN DEFAULT TRUE,
    monitor_profile BOOLEAN DEFAULT TRUE,

    is_active BOOLEAN DEFAULT TRUE,
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Monitoring alerts
CREATE TABLE monitoring_alerts (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER REFERENCES monitoring_subscriptions(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    vk_id BIGINT NOT NULL,

    alert_type VARCHAR(50), -- new_post, friend_added, friend_removed, profile_changed, etc.
    alert_data JSONB,

    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated reports
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    investigation_id INTEGER REFERENCES investigations(id) ON DELETE SET NULL,
    vk_id BIGINT NOT NULL,

    report_type VARCHAR(50) DEFAULT 'full', -- full, summary, graph_only
    file_path TEXT,
    file_size INTEGER,

    sections_included JSONB, -- ['profile', 'friends', 'analysis', 'graph']

    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- AUDIT & LOGGING
-- ============================================

-- API usage tracking (for rate limiting and billing)
CREATE TABLE api_usage_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    endpoint VARCHAR(255),
    method VARCHAR(10),
    request_params JSONB,
    response_status INTEGER,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search history
CREATE TABLE search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    search_type VARCHAR(50), -- vk, web
    search_params JSONB,
    results_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX idx_investigations_user ON investigations(user_id);
CREATE INDEX idx_analysis_tasks_user ON analysis_tasks(user_id);
CREATE INDEX idx_analysis_tasks_vk_id ON analysis_tasks(vk_id);
CREATE INDEX idx_monitoring_user ON monitoring_subscriptions(user_id);
CREATE INDEX idx_alerts_user ON monitoring_alerts(user_id);
CREATE INDEX idx_reports_user ON reports(user_id);
CREATE INDEX idx_api_usage_user ON api_usage_log(user_id, created_at);

-- Full-text search on wall posts
CREATE INDEX idx_wall_posts_text ON vk_wall_posts USING gin(to_tsvector('russian', text));
