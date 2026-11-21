/**
 * 静态站点的可配置项。
 *
 * 静态版没有后端，友链和 Giscus 配置都写在这里，改完重新 build 即可。
 */

export const site = {
  title: 'KDR 的秘境图书馆',
  subtitle: '路过的人，欢迎你，来看看吧',
  author: 'KdRefrain',
  authorAvatar: '/img/CreatorAvatar.webp',
  /** 备案号，备案通过后填写，例如：粤ICP备12345678号 */
  icp: '',
}

export interface LinkItem {
  name: string
  url: string
  description?: string
  logo?: string
}

/** 友链。静态版没有数据库，直接在这里维护。 */
export const links: LinkItem[] = [
  { name: 'GitHub', url: 'https://github.com', description: '代码托管平台' },
]

/**
 * Giscus 评论配置（基于 GitHub Discussions）。
 *
 * 仓库：https://github.com/KidoraXXX/hidden-side-kdr
 * 两个分类：Comments（文章评论）、Guestbook（留言板）。
 */
export const giscus = {
  repo: 'KidoraXXX/hidden-side-kdr',
  repoId: 'R_kgDOVFdG9w',

  /** 文章评论：按页面路径映射，每篇文章一条讨论 */
  comments: {
    category: 'Comments',
    categoryId: 'DIC_kwDOVFdG984DLgVR',
    mapping: 'pathname' as const,
  },

  /** 留言板：固定映射到同一条讨论，不随路径变化 */
  guestbook: {
    category: 'Guestbook',
    categoryId: 'DIC_kwDOVFdG984DLgVS',
    mapping: 'specific' as const,
    term: 'guestbook',
  },

  theme: 'preferred_color_scheme',
  inputPosition: 'bottom',
}
