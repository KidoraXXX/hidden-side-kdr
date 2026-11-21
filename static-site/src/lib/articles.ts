/**
 * 文章数据来自 src/pages/articles/*.md。
 *
 * 用 import.meta.glob 在构建时把每个 Markdown 文件的 frontmatter 收集起来，
 * 不依赖内容集合（content collections），这样对 Astro 版本变化不敏感。
 */

export interface ArticleFrontmatter {
  title: string
  summary?: string
  category?: string
  /** YYYY-MM-DD */
  date: string
  /** 是否在主页推荐位展示 */
  recommend?: boolean
  views?: number
  likes?: number
  comments?: number
}

export interface ArticleEntry extends ArticleFrontmatter {
  /** 页面地址，如 /articles/1 */
  url: string
  /** 文件名（不含扩展名），如 "1" */
  slug: string
}

const modules = import.meta.glob('/src/pages/articles/*.md', { eager: true }) as Record<
  string,
  { frontmatter: ArticleFrontmatter; url: string }
>

export const articles: ArticleEntry[] = Object.entries(modules)
  .map(([path, mod]) => ({
    ...mod.frontmatter,
    url: mod.url,
    slug: path.split('/').pop()!.replace(/\.md$/, ''),
  }))
  // 按日期倒序；日期相同则按文件名倒序，保证顺序稳定
  .sort((a, b) => (a.date === b.date ? b.slug.localeCompare(a.slug) : a.date < b.date ? 1 : -1))

export const recommended = articles.filter((article) => article.recommend).slice(0, 3)

export const recent = articles.slice(0, 5)

export const categories: string[] = [
  ...new Set(articles.map((article) => article.category).filter((name): name is string => Boolean(name))),
]
