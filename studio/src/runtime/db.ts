import { DatabaseSync } from 'node:sqlite'
import { ensureRuntimePaths, resolveRuntimePaths } from '../core/paths'

function ensureColumn(db: DatabaseSync, table: string, column: string, definition: string): void {
  const columns = db.prepare(`PRAGMA table_info(${table})`).all() as Array<{ name: string }>
  const hasColumn = columns.some((entry) => entry.name === column)
  if (!hasColumn) {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`)
  }
}

export function openRuntimeDb(root?: string): DatabaseSync {
  const paths = resolveRuntimePaths(root)
  ensureRuntimePaths(paths)
  const db = new DatabaseSync(paths.dbPath)

  db.exec(`
    CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY,
      workflow TEXT NOT NULL,
      brand TEXT NOT NULL,
      status TEXT NOT NULL,
      input_json TEXT NOT NULL,
      current_step TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      parent_run_id TEXT,
      error_message TEXT
    );

    CREATE TABLE IF NOT EXISTS artifacts (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      type TEXT NOT NULL,
      step TEXT NOT NULL,
      path TEXT NOT NULL,
      created_at TEXT NOT NULL,
      data_json TEXT NOT NULL
    );
  `)

  ensureColumn(db, 'runs', 'error_message', 'TEXT')

  return db
}

