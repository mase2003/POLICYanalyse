# POLICYanalyse

<p align="center">     
    <p align="center">
        <a href="https://www.antdv.com/docs/vue/introduce-cn/">
            <img src="https://img.shields.io/badge/vue-3-blue.svg" alt="bootstrap">
        </a> 
        <a href="https://v4.vitejs.dev/">
            <img src="https://img.shields.io/badge/vite-4-green.svg" alt="vite">
        </a>
        <a href="https://www.python.org/">
            <img src="https://img.shields.io/badge/Python-3-green.svg" alt="Python">
        </a>
        <a href="https://flask.palletsprojects.com/en/stable/">
            <img src="https://img.shields.io/badge/flask-3.0.3-blue.svg" alt="flask">
        </a> 
        <a href="https://redis.io/">
            <img src="https://img.shields.io/badge/redis-3.2.1-green.svg" alt="Python">
        </a>
        <a href="https://d3js.org/">
            <img src="https://img.shields.io/badge/d3-7.9.0-blue.svg" alt="d3">
        </a>  
        <a href="https://neo4j.com/">
            <img src="https://img.shields.io/badge/neo4j-5.17.0-green.svg" alt="neo4j">
        </a>
        <a href="https://echarts.apache.org/zh/index.html">
            <img src="https://img.shields.io/badge/echarts-5.5.1-blue.svg" alt="echarts">
        </a>  
        <a href="https://nginx.org/">
            <img src="https://img.shields.io/badge/nginx-1.12.2-blue.svg" alt="nginx">
        </a> 
        <a href="./LICENSE">
            <img src="https://img.shields.io/badge/license-Apache%202-red" alt="license Apache 2.0">
        </a>
    </p>
</p>

## 项目简介


基于Vue3 + Vite + Flask + Neo4j + Redis + Ant Design构建的非关系型数据库支撑的政策文件检索资料分析平台，实现地区政策自动采集 → 结构化解析 → 知识图谱可视化 → 方向判断 → 政策拆解 → 简易预测，能够帮助整理政策、内容管理、爬取等直观方式展示政策文本。

本项目适用于以下场景：

> 政策研究、课题分析数据收集、工具二次开发；  
> 政府 / 国企 / 事业单位项目申报参考准备材料；  
> 企业咨询政策报告、行业合规分析参考数据资料

## 快速链接

gitee下载地址：(https://gitee.com/mase20030409/POLICYanalyse)

github下载地址：(https://github.com/mase2003/POLICYanalyse/)

gitcode下载地址：[https://gitcode.com/mase20030409/POLICYanalyse]

试用地址(支持电脑/ipad/平板访问，页面自适应良好):[http://47.94.17.204/policy/neo4j]

## 功能演示

网站宣传视频地址：[]

## 快速启动

1. .env文件配置

```
NEO4J_URI=neo4j数据库端口地址
NEO4J_USER=名称
NEO4J_PASSWORD=密码
FLASK_PORT=端口号
VITE_API_BASE_URL=flask端口地址
ARK_API_KEY="豆包模型密匙api"
ARK_CHAT_MODEL=豆包模型名称id
REDIS_HOST=本机redis地址
REDIS_PORT=端口号
```
2. 代码文件地址配置
`policy_explain_service.py 第237行函数块的241行配置政策解读文件地址`

3. 所有内部数据文件为csv格式utf-8和txt


## 项目所需环境

请确保在项目启动之前已经运行Neo4j图数据库和Redis
```
• Python   3.11+
• Node.js  16.14.2+
• Neo4j    5.17+
• Redis    3.2.1+
• JDK      17+
```
## 开启魔法

后端运行
```
pip install -r backend/requirements.txt
python backend/app.py
```
前端运行
```
npm --prefix frontend install
npm --prefix frontend run dev
```
前端构建打包
```
npm --prefix frontend ci
npm --prefix frontend run build
```
构建产物位于 `frontend/dist/`，可由 Nginx 或静态服务托管。

## 常见问题

政策内容管理密码每天刷新，请在后端命令行查看


1. Neo4j 连接失败：检查 `.env` 账号密码与 `NEO4J_URI`，修改后重启后端。  
2. Redis 不可用：系统会自动禁用缓存并周期重连，服务可继续运行。  
3. 提供Nginx配置示例，在deploy文件夹  

## 代码结构

```
vue-neo4j-vis
├─ backend                    # 后端 (Flask 框架)
│  ├─ build                   # 构建
│  ├─ crawler_task_items      # 爬虫缓存
│  ├─ routes                  # API 路由层
│  ├─ services                # 业务逻辑层
│  ├─ utils                   # 工具函数/通用模块
│
├─ deploy                     # 部署配置
│  └─ nginx                   # Nginx 反向代理配置示例
│
├─ exports                    # 数据导出
│
├─ frontend                   # 前端应用 (Vue3 + Vite)
│  ├─ public                  # 静态公共资源
│  └─ src                     # 源码目录
│      ├─ api                 # 接口请求封装
│      ├─ assets              # 静态文件
│      ├─ components          # 公共组件
│      │  ├─ graph            # 图表组件
│      │  └─ home             # 首页/主页
│      ├─ composables         # Vue3 组合式函数
│      ├─ constants           # 常量定义
│      ├─ layout              # 布局组件
│      └─ pages               # 页面
│
├─ scripts                    # 自动化脚本
│
├─ static                     # 静态文件服务目录
│   ├─ css                    # 样式文件
│   ├─ js                     # 脚本文件
│   │  └─ external            # 第三方外部脚本
│   └─ photo                  # 图片资源
│ 
├─ .env                       # 配置文件
├─ 1.txt                      # 政策文本管理密码输出
├─ policyexplain              # 政策解读文本数据
├─ policydata                 # 政策文本数据
├─ 二十大报告.txt                 
├─ 十五五规划报告.txt
├─ 介词库.txt        
```

## 系统构成

有IP限流、密码保护、预加载缓存  
> 侧边菜单 + 顶部栏 + 内容区、莫兰迪色系  
> 前端：Vue3+Vite/Ant Design/D3.js/ECharts  
> 后端：Flask/Neo4j/Redis/Python  
> 内部依赖：jieba/beautifulsoup  
> 部署支持：Nginx   

#### 功能列举

**1. 首页看板**  
 _•政策收录数据统计、类型分布  
•最新政策列表、检索热度排行榜、轮播图_ 

**2. 政策目录**  
 _•按发布机构、地区筛选  
•按主题词筛选、分类子名单展示_ 

**3. 政策搜索**   
 _•全局政策关键词检索  
•标题、发文机构匹配  
•查看正文详情或图谱跳转_ 

**4. 图谱探索（核心）**  
 _•D3实现 知识图谱可视化   
•政策文本节点查看、节点关系扩展  
•详情正文展示  
•实时采集数据 通过分析可以图谱节点对齐  
•大模型结构化拆解政策展示知识图谱_

**5. 方向解析**  
 _•政策方向维度分析：提取文中关键词和具体方向展示  
•图谱节点 + 官方解读双域分析_ 

**6. 政策拆解（AI）**  
 _•自动提取结构文件内容导入和查看  
•试用IP 限流、自行开发使用时间自己配置api_ 

**7. 政策预测**  
 _•二十大、十五五规划文本解析  
•政策最新采集数据词频对比分析  
•关键词 / 词频 / 新词 / 消失词
•分析数据导出 Excel_ 

**8. 最新政策获取**  
 _•支持四个地区政府网站采集（广东省/北京市/上海市/四川省，后续有望解锁新地区）  
•任务进度、状态显示：采集条目，失败数据结果展示  
•文件导出 CSV/Excel  
•数据一键导入 Neo4j_ 

**9. 政策内容管理**  
 _•每日口令刷新  
•节点字段增删改  
•关系管理  
•图谱数据维护_ 

**10. 大模型服务（豆包）**   
 _•火山方舟 / 豆包模型兼容_ 


## 加入群聊

QQ交流群：1009854642，暂时不支持微信有人数限制

![输入图片说明](photo/%E5%BE%AE%E4%BF%A1%E5%9B%BE%E7%89%87_20260504225924.jpg)

## 代码贡献

开源后若有读者和各位大佬提出意见和贡献，欢迎加入，您可以创建仓库并在分支上传，后续加入仓库贡献者列表  

**爬虫低频次访问控制要求：  
禁止高频连续请求  
禁用多线程高并发爬取，采用单线程 / 低并发模式，减少对政府网站服务器的访问压力  
禁止死循环、重复请求同一页面，单次爬取任务完成后立即终止**  

如何贡献  
1、fork一份代码至自己的账号下，本地修改您要提的代码，提交至您fork的仓库  
2、登录gitee后到仓库下创建Pull Requests,选择您的仓库到common分支，提交即可  

## 外包

**如需定制功能,可以通过私信联系邮件、电话、微信等方式提交您的项目需求内容
我会出具合适的需求文件描述和工作量分析，商量合作开发项目内容金额并交付。**

## 版权说明

本项目仅供学习、研究、合法政务/企业/院校研究内部使用。
未经授权，禁止倒卖、二次分发、非法爬虫、数据泄露等行为。

**免责合规说明  
本项目爬取目标为政府部门公开政务政策文件，所有爬取逻辑严格遵守《网络安全法》《数据安全法》及政府网站爬虫协议  
禁止抓取非公开、涉密、涉及个人隐私的内容，仅爬取对外公示的公开政策信息，确保数据使用合法合规  
严格遵循政府网站协议，禁止违规爬取涉密、隐私数据  
控制访问频率，杜绝高频、并发请求对政府网站服务器造成压力  
仅抓取公开政务政策信息，不采集任何非公开、敏感数据**  

- 代码可用于个人项目或科研工具系统构建，资料爬取等使用，不要用于非法用途以防追究  
- 此项目为二次开源不建议用于盈利和商业使用 需要思考再三  
- 不要删除和修改源码的版权与作者声明及出处  
