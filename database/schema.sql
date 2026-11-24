-- Reference schema for EasyStock 1.1.0. Runtime migration is in easystock/schema.py.

PRAGMA foreign_keys=ON;

PRAGMA user_version=2;

CREATE TABLE categories (
	id INTEGER NOT NULL,
	name VARCHAR(100) NOT NULL,
	name_key VARCHAR(100) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name),
	UNIQUE (name_key)
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

CREATE TABLE warehouses (
	id INTEGER NOT NULL,
	code VARCHAR(20) NOT NULL,
	name VARCHAR(100) NOT NULL,
	address VARCHAR(200) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
);

CREATE TABLE auth_sessions (
	token_hash VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	csrf VARCHAR(64) NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (token_hash),
	FOREIGN KEY(user_id) REFERENCES users (id)
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

CREATE INDEX ix_products_name_search ON products (name_search);

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

CREATE TABLE stock_requests (
	user_id INTEGER NOT NULL,
	request_key VARCHAR(128) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	request_hash VARCHAR(64) NOT NULL,
	response_data JSON,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (user_id, request_key),
	CHECK (kind IN ('receipt','writeoff')),
	FOREIGN KEY(user_id) REFERENCES users (id)
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

CREATE TABLE stock (
	id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	warehouse_id INTEGER DEFAULT '1' NOT NULL,
	quantity INTEGER NOT NULL,
	revision INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (product_id, warehouse_id),
	CHECK (quantity BETWEEN 0 AND 1000000000),
	CHECK (revision >= 0),
	FOREIGN KEY(product_id) REFERENCES products (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX ix_stock_warehouse_product ON stock (warehouse_id, product_id);

CREATE TABLE stock_documents (
	id INTEGER NOT NULL,
	kind VARCHAR(16) NOT NULL,
	status VARCHAR(16) NOT NULL,
	warehouse_id INTEGER NOT NULL,
	destination_id INTEGER,
	supplier_id INTEGER,
	receipt_id INTEGER,
	original_id INTEGER,
	created_by_id INTEGER NOT NULL,
	posted_by_id INTEGER,
	cancelled_by_id INTEGER,
	created_at DATETIME NOT NULL,
	posted_at DATETIME,
	cancelled_at DATETIME,
	note VARCHAR(500) NOT NULL,
	revision INTEGER NOT NULL,
	PRIMARY KEY (id),
	CHECK (kind IN ('receipt','writeoff','transfer','count','reversal')),
	CHECK (status IN ('draft','review','posted','cancelled','reversed')),
	CHECK (destination_id IS NULL OR destination_id != warehouse_id),
	CHECK (revision >= 0),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(destination_id) REFERENCES warehouses (id),
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id),
	UNIQUE (receipt_id),
	FOREIGN KEY(receipt_id) REFERENCES receipts (id),
	UNIQUE (original_id),
	FOREIGN KEY(original_id) REFERENCES stock_documents (id),
	FOREIGN KEY(created_by_id) REFERENCES users (id),
	FOREIGN KEY(posted_by_id) REFERENCES users (id),
	FOREIGN KEY(cancelled_by_id) REFERENCES users (id)
);

CREATE INDEX ix_stock_documents_status_date ON stock_documents (status, created_at);

CREATE TABLE stock_document_lines (
	id INTEGER NOT NULL,
	document_id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	quantity INTEGER NOT NULL,
	price_cents INTEGER,
	expected_quantity INTEGER,
	expected_revision INTEGER,
	PRIMARY KEY (id),
	UNIQUE (document_id, product_id),
	CHECK (quantity BETWEEN 0 AND 1000000000),
	CHECK (price_cents IS NULL OR price_cents >= 0),
	FOREIGN KEY(document_id) REFERENCES stock_documents (id),
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE stock_movements (
	id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	receipt_id INTEGER,
	warehouse_id INTEGER DEFAULT '1' NOT NULL,
	document_id INTEGER,
	type VARCHAR(20) NOT NULL,
	quantity INTEGER NOT NULL,
	balance_after INTEGER NOT NULL,
	note VARCHAR(500) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CHECK (type IN ('receipt', 'transfer_in', 'adjustment_in', 'reversal_in', 'writeoff', 'transfer_out', 'adjustment_out', 'reversal_out')),
	CHECK (quantity > 0),
	CHECK (balance_after >= 0),
	FOREIGN KEY(product_id) REFERENCES products (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(receipt_id) REFERENCES receipts (id),
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id),
	FOREIGN KEY(document_id) REFERENCES stock_documents (id)
);

CREATE INDEX ix_stock_movements_created_at ON stock_movements (created_at);

CREATE INDEX ix_stock_movements_document_id ON stock_movements (document_id);

CREATE INDEX ix_stock_movements_product_id ON stock_movements (product_id);

CREATE INDEX ix_stock_movements_warehouse_date ON stock_movements (warehouse_id, created_at);

INSERT INTO warehouses (id, code, name, address) VALUES (1, 'MAIN', 'Основний склад', '');
