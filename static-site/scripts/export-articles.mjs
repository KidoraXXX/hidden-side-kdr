/**
 * 把 MySQL 里的文章导出为 Astro 的 Markdown 页面。
 *
 * 每篇文章生成 src/pages/articles/<id>.md，frontmatter 带上标题、分类、日期、
 * 推荐标记与统计数字，正文原样写入。
 *
 * 数据库凭据**不写死在脚本里**，按以下顺序获取：
 *   1. 环境变量 DB_USERNAME / DB_PASSWORD / DB_URL
 *   2. backend/backend/env.local.json（该文件已被 .gitignore 忽略）
 *
 * 用法：
 *   node scripts/export-articles.mjs
 */
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const outputDir = resolve(here, '../src/pages/articles')
const localEnvPath = resolve(here, '../../backend/backend/env.local.json')

function loadCredentials() {
  if (process.env.DB_USERNAME && process.env.DB_PASSWORD) {
    return {
      username: process.env.DB_USERNAME,
      password: process.env.DB_PASSWORD,
      url: process.env.DB_URL,
    }
  }

  if (existsSync(localEnvPath)) {
    const env = JSON.parse(readFileSync(localEnvPath, 'utf8'))
    if (env.DB_USERNAME && env.DB_PASSWORD) {
      return { username: env.DB_USERNAME, password: env.DB_PASSWORD, url: env.DB_URL }
    }
  }

  throw new Error(
    `缺少数据库凭据：请设置环境变量 DB_USERNAME / DB_PASSWORD，或在 ${localEnvPath} 提供 env.local.json`,
  )
}

function parseJdbcUrl(url) {
  const matched = /^jdbc:mysql:\/\/([^:/]+)(?::(\d+))?\/([^?]+)/.exec(url ?? '')
  return {
    host: process.env.MYSQL_HOST ?? matched?.[1] ?? 'localhost',
    port: process.env.MYSQL_PORT ?? matched?.[2] ?? '3306',
    database: process.env.MYSQL_DATABASE ?? matched?.[3] ?? 'hidden_side_kdr',
  }
}

const credentials = loadCredentials()
const target = parseJdbcUrl(credentials.url)

const sql = `
SELECT JSON_OBJECT(
  'id', a.id,
  'title', a.title,
  'summary', a.summary,
  'content', a.content_md,
  'category', c.name,
  'recommend', a.is_recommend = 1,
  'views', a.view_count,
  'likes', a.like_count,
  'comments', a.comment_count,
  'date', DATE_FORMAT(a.create_time, '%Y-%m-%d')
)
FROM article a
LEFT JOIN category c ON c.id = a.category_id
WHERE a.status = 1
ORDER BY a.id;
`

const output = execFileSync(
  'mysql',
  [
    '-h',
    target.host,
    '-P',
    target.port,
    '-u',
    credentials.username,
    `-p${credentials.password}`,
    '--default-character-set=utf8mb4',
    '--batch',
    '--raw',
    '--skip-column-names',
    target.database,
    '-e',
    sql,
  ],
  { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 },
)

const rows = output
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter(Boolean)
  .map((line) => JSON.parse(line))

mkdirSync(outputDir, { recursive: true })

for (const row of rows) {
  const yaml = [
    '---',
    'layout: ../../layouts/ArticleLayout.astro',
    `title: ${JSON.stringify(row.title ?? '')}`,
    `summary: ${JSON.stringify(row.summary ?? '')}`,
    `category: ${JSON.stringify(row.category ?? '')}`,
    `date: ${JSON.stringify(row.date ?? '1970-01-01')}`,
    `recommend: ${row.recommend ? 'true' : 'false'}`,
    `views: ${Number(row.views) || 0}`,
    `likes: ${Number(row.likes) || 0}`,
    `comments: ${Number(row.comments) || 0}`,
    '---',
  ].join('\n')

  // 清洗空 host 的图片链接（如 ![](https://)）：Astro 会把它当成资源导入而构建失败
  const body = (row.content ?? '')
    .replace(/\r\n/g, '\n')
    .replace(/!\[[^\]]*\]\(https?:\/\/\)/g, '')

  writeFileSync(resolve(outputDir, `${row.id}.md`), `${yaml}\n\n${body}\n`, 'utf8')
}

console.log(`已导出 ${rows.length} 篇文章到 ${outputDir}`)
