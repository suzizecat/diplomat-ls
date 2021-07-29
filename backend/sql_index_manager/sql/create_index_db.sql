CREATE TABLE IF NOT EXISTS files
(
	id INTEGER PRIMARY KEY,
	path TEXT UNIQUE NOT NULL,
	content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anchors
(
	id integer primary key,
	file text not null,
	start_line integer not null,
	start_char integer not null,
	stop_line integer not null,
	stop_char integer not null

	-- Unique on file + start + end
);

CREATE TABLE IF NOT EXISTS symbols
(
	id  INTEGER PRIMARY KEY,
	name   TEXT, -- Not unique across files
	type TEXT,
	declaration_anchor INTEGER REFERENCES  anchors(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS refs
(
	id INTEGER PRIMARY KEY,
	anchor INTEGER NOT NULL REFERENCES  anchors(id) ON DELETE CASCADE,
	symbol INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE  TABLE IF NOT EXISTS relationships
(
	id INTEGER PRIMARY KEY,
	parent INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
	child INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE VIEW IF NOT EXISTS  fully_qualified_symbols
(
	sid, name, type, aid, file, start_line, start_char, stop_line, stop_char, path
) AS
SELECT symbols.id, name, type, anchors.id, file, start_line, start_char, stop_line, stop_char, files.path FROM symbols
		INNER JOIN anchors ON anchors.id == declaration_anchor
		INNER JOIN files ON files.id == file