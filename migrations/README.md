# Migrations

SQLite 表结构由 `app.db.migrations.run_pending()` 按文件名顺序执行。

规则：

- 迁移文件放在本目录，命名格式为 `0001_xxx.sql`、`0002_xxx.sql`。
- 每个迁移文件执行成功后会写入 `schema_migrations.version`。
- 迁移 SQL 应尽量保持可重复安全，例如使用 `CREATE TABLE IF NOT EXISTS`、`CREATE INDEX IF NOT EXISTS`。
- `app.db.cache.ensure()` 会在首次数据库访问时自动执行待执行迁移。
