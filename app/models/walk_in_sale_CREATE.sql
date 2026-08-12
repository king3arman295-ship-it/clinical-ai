-- Run once if alembic is not used:
CREATE TABLE IF NOT EXISTS pharmacy_walk_in_sales (
  id SERIAL PRIMARY KEY,
  medicine_id INTEGER NOT NULL REFERENCES medicines(id),
  quantity INTEGER NOT NULL DEFAULT 1,
  patient_id INTEGER NULL REFERENCES patients(id),
  customer_name VARCHAR(200) NULL,
  customer_phone VARCHAR(50) NULL,
  notes TEXT NULL,
  unit_price DOUBLE PRECISION NOT NULL DEFAULT 0,
  total_price DOUBLE PRECISION NOT NULL DEFAULT 0,
  sold_by INTEGER NULL REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
