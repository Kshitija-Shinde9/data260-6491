-- HW9 Part 1. Safe to run once on an existing s6491_rel database.
-- The app also adds this column on startup when it is missing.
ALTER TABLE recalls ADD COLUMN view_count INT NOT NULL DEFAULT 0;
