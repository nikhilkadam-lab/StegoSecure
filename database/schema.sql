
CREATE DATABASE IF NOT EXISTS stego_secure
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE stego_secure;

CREATE TABLE users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE admins (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_admins_username (username),
    UNIQUE KEY uq_admins_email (email)
) ENGINE=InnoDB;

CREATE TABLE plans (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    encryptions INT UNSIGNED NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_plans_price CHECK (price >= 0)
) ENGINE=InnoDB;

CREATE TABLE system_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value INT NOT NULL
) ENGINE=InnoDB;

CREATE TABLE encryption_limits (
    user_id INT UNSIGNED PRIMARY KEY,
    remaining_attempts INT UNSIGNED NOT NULL DEFAULT 5,
    CONSTRAINT chk_remaining_attempts
        CHECK (remaining_attempts >= 0),
    CONSTRAINT fk_limits_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE gallery (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255) NULL,
    output_filename VARCHAR(255) NULL,
    file_size_bytes BIGINT UNSIGNED NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_gallery_user_date (user_id, uploaded_at),
    CONSTRAINT fk_gallery_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE payments (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    plan_id INT UNSIGNED NOT NULL,
    payment_id VARCHAR(100) NULL,
    razorpay_order_id VARCHAR(100) NULL,
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_payments_payment_id (payment_id),
    UNIQUE KEY uq_payments_order_id (razorpay_order_id),
    KEY idx_payments_user_date (user_id, created_at),
    KEY idx_payments_status (status),
    CONSTRAINT chk_payment_amount CHECK (amount >= 0),
    CONSTRAINT fk_payments_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_payments_plan
        FOREIGN KEY (plan_id) REFERENCES plans(id)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

INSERT INTO system_settings (setting_key, setting_value)
VALUES ('default_encryption_limit', 5);
