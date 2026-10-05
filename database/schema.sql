-- Reference schema generated from actual SQLAlchemy models.
PRAGMA foreign_keys=ON;

CREATE TABLE auth_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	csrf VARCHAR(64) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE categories (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	name_key VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	UNIQUE (name_key)
);

CREATE TABLE products (
	id INTEGER NOT NULL, 
	sku VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	name_search VARCHAR(200) NOT NULL, 
	category_id INTEGER NOT NULL, 
	supplier_id INTEGER, 
	price_cents INTEGER NOT NULL, 
	min_stock INTEGER NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	archived BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (price_cents >= 0), 
	CHECK (min_stock >= 0), 
	UNIQUE (sku), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE TABLE receipt_items (
	id INTEGER NOT NULL, 
	receipt_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	price_cents INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity > 0), 
	CHECK (price_cents >= 0), 
	FOREIGN KEY(receipt_id) REFERENCES receipts (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE receipts (
	id INTEGER NOT NULL, 
	supplier_id INTEGER, 
	user_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	note VARCHAR(500) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE stock (
	id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (quantity >= 0), 
	UNIQUE (product_id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE stock_movements (
	id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	receipt_id INTEGER, 
	type VARCHAR(20) NOT NULL, 
	quantity INTEGER NOT NULL, 
	balance_after INTEGER NOT NULL, 
	note VARCHAR(500) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (type IN ('receipt','writeoff')), 
	CHECK (quantity > 0), 
	CHECK (balance_after >= 0), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(receipt_id) REFERENCES receipts (id)
);

CREATE TABLE suppliers (
	id INTEGER NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	phone VARCHAR(40) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role IN ('admin','keeper','manager')), 
	UNIQUE (email)
);

CREATE INDEX ix_products_name_search ON products (name_search);

CREATE INDEX ix_stock_movements_created_at ON stock_movements (created_at);

CREATE INDEX ix_stock_movements_product_id ON stock_movements (product_id);
