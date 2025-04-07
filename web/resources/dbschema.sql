CREATE TABLE `files` (
  `id` integer PRIMARY KEY,
  `local_path` STRING,
  `file_indices` TEXT,
  `is_uploaded` bool
);

CREATE TABLE `mega_accounts` (
  `id` integer PRIMARY KEY,
  `email` STRING,
  `password` STRING,
  `is_pro_account` bool,
  `used_quota` STRING,
  `total_quota` STRING,
  `storage_quota_updated` timestamp,
  `last_login` timestamp
);

CREATE TABLE `mega_files` (
  `id` integer PRIMARY KEY,
  `file_id` integer,
  `account_id` integer,
  `is_local` bool,
  `sharing_link` STRING,
  `sharing_link_expiry` timestamp,
  `file_indices` TEXT,
  FOREIGN KEY (account_id) REFERENCES mega_accounts (id),
  FOREIGN KEY (file_id) REFERENCES files (id)
);