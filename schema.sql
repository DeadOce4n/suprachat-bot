CREATE DATABASE IF NOT EXISTS sc_admin;

CREATE TABLE IF NOT EXISTS channel(
	channel_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
	channel_name VARCHAR(64) NOT NULL,
	badwords_enabled BOOLEAN NOT NULL DEFAULT false,
	badnicks_enabled BOOLEAN NOT NULL DEFAULT false,
	rules_enabled BOOLEAN NOT NULL DEFAULT false,
);

CREATE TABLE IF NOT EXISTS badword(
	badword VARCHAR(100) NOT NULL,
	channel_id INT NOT NULL,
	PRIMARY KEY(badword, channel_id),
	FOREIGN KEY(channel_id) REFERENCES channel(channel_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS badnick(
	badnick VARCHAR(32) NOT NULL,
	channel_id INT NOT NULL,
	PRIMARY KEY(badnick, channel_id)
	FOREIGN KEY(channel_id) REFERENCES channel(channel_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rule(
	rule_number INT NOT NULL,
	channel_id INT NOT NULL,
	rule_desc TEXT NOT NULL,
	PRIMARY KEY(rule_number, channel_id),
	FOREIGN KEY(channel_id) REFERENCES channel(channel_id) ON DELETE CASCADE
);
