CREATE TABLE categories (
	id int NOT NULL,
	name varchar(255) NULL
)

ALTER TABLE categories ADD CONSTRAINT PK_categories PRIMARY KEY CLUSTERED (
	id
)

CREATE TABLE news (
	id int NOT NULL,
	link varchar(90) NOT NULL,
	title varchar(127) NOT NULL,
	excerpt text NOT NULL,
	date_first_published datetime NOT NULL,
	date_last_published datetime NOT NULL,
	text text NOT NULL,
	html_text text NOT NULL
)

ALTER TABLE news ADD CONSTRAINT PK_news PRIMARY KEY CLUSTERED (
	id
)

CREATE TABLE news_category (
	news_id int NOT NULL,
	category_id int NOT NULL
)

ALTER TABLE news_category ADD CONSTRAINT PK_news_category PRIMARY KEY CLUSTERED (
	news_id,
	category_id
)

CREATE TABLE comments (
	id int NOT NULL,
	news_id int NOT NULL,
	author varchar(200) NOT NULL,
	date_published datetime NOT NULL,
	likes int NOT NULL,
	dislikes int NOT NULL,
	text text NOT NULL,
	html_text text NOT NULL
)

ALTER TABLE comments ADD CONSTRAINT PK_comments PRIMARY KEY CLUSTERED (
	id
)

ALTER TABLE comments ADD CONSTRAINT FK_comments_news FOREIGN KEY (
	news_id
) REFERENCES news (
	id
)
ON UPDATE  NO ACTION 
ON DELETE  NO ACTION