import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from './layout/MainLayout.vue'
import GraphExplorerPage from './pages/GraphExplorerPage.vue'
import OfficialReadPage from './pages/OfficialReadPage.vue'
import DirectionAnalysisPage from './pages/DirectionAnalysisPage.vue'
import PolicyCatalogPage from './pages/PolicyCatalogPage.vue'
import SearchTablePage from './pages/SearchTablePage.vue'
import SimpleListPage from './pages/SimpleListPage.vue'
import HomePage from './pages/HomePage.vue'
import LatestPolicyFetchPage from './pages/LatestPolicyFetchPage.vue'
import FifteenFivePlanPage from './pages/FifteenFivePlanPage.vue'
import PartyTwentyReportPage from './pages/PartyTwentyReportPage.vue'
import CrawlerPolicyParsePage from './pages/CrawlerPolicyParsePage.vue'
import PolicyDeconstructPlaceholderPage from './pages/PolicyDeconstructPlaceholderPage.vue'
import PolicyContentManagePage from './pages/PolicyContentManagePage.vue'

const routes = [
  { path: '/', redirect: '/neo4j' },
  {
    path: '/neo4j',
    component: MainLayout,
  },
  {
    path: '/main',
    component: GraphExplorerPage,
  },
]

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

/** 侧栏 menuKey → 页面组件与 props */
export const menuRegistry = {
  home: {
    component: HomePage,
    title: '首页',
    props: {},
  },
  catalogOrg: {
    component: PolicyCatalogPage,
    title: '发布机构筛选',
    props: { mode: 'org' },
  },
  catalogTopic: {
    component: PolicyCatalogPage,
    title: '主题词筛选',
    props: { mode: 'topic' },
  },
  graphPolicy: {
    component: GraphExplorerPage,
    title: '单条政策文本知识图谱解析',
    props: { variant: 'policyArticle' },
  },
  officialRead: {
    component: OfficialReadPage,
    title: '官方解读',
    props: {},
  },
  directionAnalysis: {
    component: DirectionAnalysisPage,
    title: '方向解析',
    props: {},
  },
  policyDeconstruct: {
    component: PolicyDeconstructPlaceholderPage,
    title: '政策拆解',
    props: {},
  },
  forecastFifteen: {
    component: FifteenFivePlanPage,
    title: '十五五规划解析',
    props: {},
  },
  forecastParty20: {
    component: PartyTwentyReportPage,
    title: '二十大报告解析',
    props: {},
  },
  forecastCrawler: {
    component: CrawlerPolicyParsePage,
    title: '政策采集解析',
    props: {},
  },
  /** 兼容旧侧栏键，等同于十五五规划解析 */
  forecast: {
    component: FifteenFivePlanPage,
    title: '十五五规划解析',
    props: {},
  },
  latestPolicyFetch: {
    component: LatestPolicyFetchPage,
    title: '最新政策获取',
    props: {},
  },
  policyContentManage: {
    component: PolicyContentManagePage,
    title: '政策内容管理',
    props: {},
  },
}

/** 兼容旧 pageRegistry 键名（若仍有引用） */
export const pageRegistry = {
  first: HomePage,
  catalog: PolicyCatalogPage,
  catalog1: PolicyCatalogPage,
  read: SearchTablePage,
  file: SearchTablePage,
  forecast: FifteenFivePlanPage,
  high: SimpleListPage,
  AuthorArticleSearch: GraphExplorerPage,
  pageKnowlegGraph: GraphExplorerPage,
  pageNeovis: GraphExplorerPage,
}
