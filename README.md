# Auto Zotero Collector

🚀 自动从 PubMed 采集论文到 Zotero 的工具，支持 GitHub Actions 定时运行。

## 功能特点

- ✅ **自动采集**: 从 PubMed 检索符合条件的论文
- ✅ **智能去重**: 记录已处理的 PMID，避免重复导入
- ✅ **主题分类**: 10 个预定义主题，自动打标签
- ✅ **定时运行**: GitHub Actions 每天自动执行
- ✅ **手动触发**: 支持 workflow_dispatch 手动运行
- ✅ **状态持久化**: 通过 git commit 保存采集状态

## 快速开始

### 1. Fork 或克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/auto-zotero-collector.git
cd auto-zotero-collector
```

### 2. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|------------|------|
| `ZOTERO_USER_ID` | 你的 Zotero 用户 ID |
| `ZOTERO_API_KEY` | 你的 Zotero API Key |

### 3. 启用 GitHub Actions

进入 Actions 页面，启用工作流。定时任务将在每天 UTC 22:00（北京时间早上 6:00）自动运行。

### 4. 手动触发（可选）

在 Actions 页面点击 "Run workflow" 可以手动触发采集，支持自定义参数：
- **days_back**: 检索最近多少天的论文（默认 30）
- **topic**: 指定主题（留空则处理所有主题）
- **dry_run**: 预览模式（不实际写入）

## 本地运行

### 安装依赖

```bash
pip install -r requirements.txt
```

### 设置环境变量

```bash
# Windows PowerShell
$env:ZOTERO_USER_ID = "你的用户ID"
$env:ZOTERO_API_KEY = "你的API密钥"

# Linux/macOS
export ZOTERO_USER_ID="你的用户ID"
export ZOTERO_API_KEY="你的API密钥"
```

### 运行脚本

```bash
# 基本用法
python scripts/auto_pubmed_pmc_to_zotero.py

# 指定天数
python scripts/auto_pubmed_pmc_to_zotero.py --days 7

# 预览模式
python scripts/auto_pubmed_pmc_to_zotero.py --dry-run

# 查看状态
python scripts/auto_pubmed_pmc_to_zotero.py --status

# 列出主题
python scripts/auto_pubmed_pmc_to_zotero.py --list-topics

# 指定主题
python scripts/auto_pubmed_pmc_to_zotero.py --topic PMC_Vg_Hormone_Lep
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--days N` | 检索最近 N 天的论文 | 30 |
| `--retmax N` | 每个主题最多检索多少条 | 200 |
| `--topic NAME` | 只处理指定主题 | 全部 |
| `--dry-run` | 预览模式，不写入 Zotero | false |
| `--status` | 显示采集状态 | - |
| `--list-topics` | 列出所有可用主题 | - |
| `--output FILE` | 输出结果到 JSON 文件 | - |
| `--state-file FILE` | 状态文件路径 | auto_pubmed_state.json |
| `--log-file FILE` | 日志输出到文件 | - |
| `--verbose` | 显示详细日志 | false |

## 预定义主题

| 主题名称 | 检索内容 |
|----------|----------|
| PMC_20Eonly_Vg_Lep | 蜕皮激素 + 卵黄蛋白 + 鳞翅目 |
| PMC_JHonly_Vg_Lep | 保幼激素 + 卵黄蛋白 + 鳞翅目 |
| PMC_LifeHistory_Vg_Lep | 生活史 + 卵黄蛋白 + 鳞翅目 |
| PMC_Ovary_Repro_Vg_Lep | 卵巢 + 生殖 + 卵黄蛋白 + 鳞翅目 |
| PMC_Nutrition_Hormone_Vg_Lep | 营养 + 激素 + 卵黄蛋白 + 鳞翅目 |
| PMC_Hormone_LifeHistory_Lep | 激素 + 生活史 + 鳞翅目 |
| PMC_Hormone_Ovary_Lep | 激素 + 卵巢 + 鳞翅目 |
| PMC_Vg_ReproMode_Lep | 卵黄蛋白 + 生殖模式 + 鳞翅目 |
| PMC_Vg_Ovary_Lep | 卵黄蛋白 + 卵巢 + 鳞翅目 |
| PMC_Vg_Hormone_Lep | 卵黄蛋白 + 激素 + 鳞翅目 |

## 文件结构

```
auto-zotero-collector/
├── .github/
│   └── workflows/
│       └── daily-collect.yml    # GitHub Actions 配置
├── scripts/
│   └── auto_pubmed_pmc_to_zotero.py  # 采集脚本
├── requirements.txt             # Python 依赖
├── auto_pubmed_state.json       # 状态文件（自动生成）
└── README.md                    # 项目说明
```

## 工作流集成

本工具是文献管理自动化工作流的第一环节：

```
┌─────────────────────────────────────────────────────────────┐
│                    文献管理自动化工作流                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [GitHub Actions] ──每天6:00──→ auto-zotero-collector       │
│                                       │                     │
│                                       ↓                     │
│                                 Zotero 文献库                │
│                                       │                     │
│                                       ↓                     │
│                              /paper-triage                  │
│                              (智能筛选论文)                  │
│                                       │                     │
│                          ┌────────────┴────────────┐        │
│                          ↓                         ↓        │
│                  /paper-summarize            /paper-qa      │
│                  (综述生成)                  (问答/初稿)     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 获取 Zotero API 凭证

1. 登录 [Zotero 官网](https://www.zotero.org/)
2. 进入 Settings → Feeds/API
3. 查看你的 User ID
4. 创建新的 API Key，勾选以下权限：
   - Allow library access
   - Allow write access

## 常见问题

### Q: 采集的论文在 Zotero 哪里？

采集的论文会添加到 Zotero 库的根目录，并带有以下标签：
- `auto:pubmed` - 标识为自动采集
- `topic:主题名称` - 标识所属主题

### Q: 如何修改检索关键词？

编辑 `scripts/auto_pubmed_pmc_to_zotero.py` 文件中的关键词定义（LEP、VG、HORM 等变量）。

### Q: GitHub Actions 运行失败怎么办？

1. 检查 Secrets 是否正确配置
2. 查看 Actions 运行日志
3. 确认 Zotero API Key 权限是否足够

### Q: 如何更改定时运行时间？

编辑 `.github/workflows/daily-collect.yml` 中的 cron 表达式：
```yaml
schedule:
  - cron: '0 22 * * *'  # UTC 时间，北京时间 +8
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
