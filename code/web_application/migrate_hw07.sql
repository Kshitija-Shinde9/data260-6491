-- Run once against the existing s6491_rel database.
-- If these columns already exist, skip the corresponding ALTER statements.

ALTER TABLE users ADD COLUMN username VARCHAR(100) NULL;
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'reader';

UPDATE users
SET username = CASE
    WHEN email = 'admin@s6491.com' THEN 'admin'
    ELSE SUBSTRING_INDEX(email, '@', 1)
END
WHERE username IS NULL;

ALTER TABLE users MODIFY username VARCHAR(100) NOT NULL;
CREATE UNIQUE INDEX uq_users_username ON users(username);

UPDATE users SET role = 'moderator' WHERE username = 'admin';
