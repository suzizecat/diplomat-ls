CREATE TABLE IF NOT EXISTS files
(
	id INTEGER PRIMARY KEY,
	path TEXT UNIQUE NOT NULL,
	content TEXT NOT NULL
);

create table if not exists anchors
(
	id integer primary key,
	file text not null,
	start integer not null,
	stop integer not null

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

CREATE VIEW IF NOT EXISTS  fully_qualified_symbols
(
	sid, name, type, aid, file, start, stop, path
) AS
SELECT symbols.id, name, type, anchors.id, file, start, stop, files.path FROM symbols
		INNER JOIN anchors ON anchors.id == declaration_anchor
		INNER JOIN files ON files.id == file