USE stegosecure;

-- =========================================================
-- 1. PLANS
-- =========================================================

CREATE TABLE IF NOT EXISTS plans (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    encryption_count INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_plans_name (name)
) ENGINE=InnoDB;


-- =========================================================
-- 2. SYSTEM SETTINGS
-- Flexible key/value settings for admin configuration.
-- =========================================================

CREATE TABLE IF NOT EXISTS system_settings (
    id INT NOT NULL AUTO_INCREMENT,
    setting_key VARCHAR(100) NOT NULL,
    setting_value VARCHAR(500) NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_system_settings_key (setting_key)
) ENGINE=InnoDB;


-- =========================================================
-- 3. ENCRYPTION LIMITS / USAGE
-- One row per user.
-- =========================================================

CREATE TABLE IF NOT EXISTS encryption_limits (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    remaining_encryptions INT NOT NULL DEFAULT 0,
    total_used INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_encryption_limits_user (user_id),
    CONSTRAINT fk_encryption_limits_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =========================================================
-- 4. GALLERY / PREVIOUS ENCRYPTIONS
--
-- storage_key is deliberately generic:
-- local filesystem now
-- S3 object key later
--
-- No encryption key, QA answer, SHA-256 key, or encrypted
-- payload is stored here.
-- =========================================================

CREATE TABLE IF NOT EXISTS gallery (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,

    storage_key VARCHAR(500) NOT NULL,

    original_cover_filename VARCHAR(255) NOT NULL,
    output_filename VARCHAR(255) NOT NULL,

    payload_type ENUM('TEXT', 'FILE') NOT NULL,
    hidden_filename VARCHAR(255) NULL,

    cover_width INT NOT NULL,
    cover_height INT NOT NULL,

    output_size_bytes BIGINT UNSIGNED NULL,

    status ENUM('SUCCESS', 'FAILED') NOT NULL DEFAULT 'SUCCESS',

    created_at DATETIME NOT NULL,

    PRIMARY KEY (id),

    KEY idx_gallery_user_created (user_id, created_at),

    CONSTRAINT fk_gallery_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =========================================================
-- 5. PAYMENTS
--
-- Prepared for Razorpay.
-- Signature verification will be implemented in the
-- payment service later.
-- =========================================================

CREATE TABLE IF NOT EXISTS payments (
    id INT NOT NULL AUTO_INCREMENT,

    user_id INT NOT NULL,
    plan_id INT NULL,

    razorpay_order_id VARCHAR(100) NULL,
    razorpay_payment_id VARCHAR(100) NULL,
    razorpay_signature VARCHAR(255) NULL,

    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',

    status ENUM(
        'CREATED',
        'PENDING',
        'SUCCESS',
        'FAILED',
        'REFUNDED'
    ) NOT NULL DEFAULT 'CREATED',

    created_at DATETIME NOT NULL,
    verified_at DATETIME NULL,

    PRIMARY KEY (id),

    UNIQUE KEY uq_payments_order_id (razorpay_order_id),
    UNIQUE KEY uq_payments_payment_id (razorpay_payment_id),

    KEY idx_payments_user_created (user_id, created_at),

    CONSTRAINT fk_payments_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_payments_plan
        FOREIGN KEY (plan_id)
        REFERENCES plans(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
) ENGINE=InnoDB;