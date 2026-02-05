#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
auto_pubmed_pmc_to_zotero.py

功能：
- 使用固定的 10 个 TOPIC，从 PubMed 自动检索鳞翅目 + Vg 等相关文献
- 新文献写入 Zotero 指定子集合，并打上 auto:pubmed + topic:XXX 标签
- 使用 auto_pubmed_state.json 记录已处理 PMID，避免重复导入
- 支持命令行参数配置
- 支持 GitHub Actions 定时运行

依赖：
- requests
- 环境变量：ZOTERO_USER_ID, ZOTERO_API_KEY

版本：v5.0 - 优化版，支持 GitHub Actions
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
import warnings

# 禁用 SSL 警告（仅用于测试）
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= 版本信息 =================
__version__ = "5.0.0"

# ================= 日志设置 =================

def setup_logging(log_file: Optional[str] = None, verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )
    return logging.getLogger(__name__)

# ================= NCBI & Zotero 配置 =================

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

ZOTERO_USER_ID = os.environ.get("ZOTERO_USER_ID")
ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY")

STATE_FILE = "auto_pubmed_state.json"

DEFAULT_DAYS_BACK = 30
DEFAULT_RETMAX = 200

# ================= 创建健壮的 Session =================

def create_robust_session() -> requests.Session:
    """创建带重试机制和超时配置的 Session"""
    session = requests.Session()

    # 配置重试策略
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    return session

# 创建全局 session
SESSION = create_robust_session()

# ================= 关键词模块 =================

LEP = '(Lepidoptera OR moth* OR butterfly* OR "silkworm" OR Bombyx OR Antheraea OR Samia OR Manduca OR Helicoverpa OR Spodoptera OR Cydia OR Ostrinia OR Galleria OR Hyphantria OR Grapholita OR Papilio OR Pieris OR Danaus OR Hyles OR Plutella OR Agrotis OR Mythimna)'

VG = '("vitellogenin" OR "vitellogenesis" OR "vitellin" OR "VgR" OR "vitellogenin receptor" OR "yolk protein" OR "yolk" OR "egg yolk" OR "fat body" OR "oocyte development" OR "oocyte maturation" OR "vitellogenic stage" OR "vitellogenic oocyte")'

HORM = '("juvenile hormone" OR JH OR methoprene OR Met OR Taiman OR "Kr-h1" OR ecdysone OR 20E OR "20-hydroxyecdysone" OR "ecdysteroid" OR EcR OR USP OR "Broad-Complex" OR Br-C OR "hormone receptor" OR "steroid hormones" OR "endocrine regulation" OR "steroid receptor" OR "gonadotropic" OR "gonadotrophic" OR insulin OR "insulin-like peptide" OR IIS OR TOR OR "JH esterase" OR "JH epoxide hydrolase" OR JHAMT OR neuroendocrine OR "steroidogenic pathway" OR "hormone signaling")'

HORM_20E = '(ecdysone OR 20E OR "20-hydroxyecdysone" OR "ecdysteroid" OR EcR OR USP OR "Broad-Complex" OR Br-C OR "steroid hormones" OR "steroid receptor" OR "steroidogenic pathway")'
HORM_JH = '("juvenile hormone" OR JH OR methoprene OR Met OR Taiman OR "Kr-h1" OR "JH esterase" OR "JH epoxide hydrolase" OR JHAMT)'

OVARY = '(panoistic OR meroistic OR telotrophic OR polytrophic OR ovariole* OR oogenesis OR ovary OR ovarian OR "oocyte maturation" OR "ovarian development" OR "ovarian follicle" OR germarium OR "nurse cell" OR "follicular epithelium" OR "chorion formation")'

REPRO = '(viviparity OR ovoviviparity OR oviparity OR parthenogenesis OR paedogenesis OR "reproductive strategy" OR "reproductive physiology" OR "reproductive diapause" OR "reproductive output" OR "mating behavior" OR "female reproduction" OR "male reproduction" OR "egg production" OR "egg laying" OR oviposition OR fecundity OR fertility)'

LIFE = '("life history" OR "life-history" OR lifehistory OR "life span" OR longevity OR "developmental duration" OR "development time" OR "postembryonic development" OR metamorphosis OR "pupal stage" OR "larval stage" OR "adult longevity" OR "reproductive lifespan" OR diapause OR "seasonal reproduction")'

DIET = '("feeding behavior" OR "adult feeding" OR "feeding ecology" OR diet OR "nutritional regulation" OR "nutrient signaling" OR "sugar feeding" OR "nectar feeding" OR "amino acid" OR "lipid metabolism" OR "carbohydrate metabolism" OR "feeding adaptation" OR "nutritional stress" OR "nutrient limitation")'

EXCLUDE = 'NOT (Drosophila OR Diptera OR bee OR Apis OR Hymenoptera OR beetle OR Coleoptera OR mosquito OR Aedes OR Anopheles OR locust OR Orthoptera OR Blattodea OR human OR mouse OR rat OR mammal OR plant OR fish OR bacteria OR virus OR yeast OR fungus OR turtle OR snake OR cannabis)'

# ================= TOPIC 配置 =================

TOPICS: List[Dict] = [
    {
        "name": "PMC_20Eonly_Vg_Lep",
        "collection": "V6WK5UBC",
        "query": f"{LEP} AND {VG} AND {HORM_20E} AND {EXCLUDE}",
    },
    {
        "name": "PMC_JHonly_Vg_Lep",
        "collection": "V7BG9W57",
        "query": f"{LEP} AND {VG} AND {HORM_JH} AND {EXCLUDE}",
    },
    {
        "name": "PMC_LifeHistory_Vg_Lep",
        "collection": "A44KVBVZ",
        "query": f"{LEP} AND {VG} AND {LIFE} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Ovary_Repro_Vg_Lep",
        "collection": "FX77FAZX",
        "query": f"{LEP} AND {VG} AND {OVARY} AND {REPRO} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Nutrition_Hormone_Vg_Lep",
        "collection": "658NHUVA",
        "query": f"{LEP} AND {VG} AND {DIET} AND {HORM} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Hormone_LifeHistory_Lep",
        "collection": "XR58SBTF",
        "query": f"{LEP} AND {HORM} AND {LIFE} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Hormone_Ovary_Lep",
        "collection": "4SPN8P38",
        "query": f"{LEP} AND {HORM} AND {OVARY} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Vg_ReproMode_Lep",
        "collection": "EMWGGGQM",
        "query": f"{LEP} AND {VG} AND {REPRO} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Vg_Ovary_Lep",
        "collection": "5WVANIIZ",
        "query": f"{LEP} AND {VG} AND {OVARY} AND {EXCLUDE}",
    },
    {
        "name": "PMC_Vg_Hormone_Lep",
        "collection": "3JDKU2AH",
        "query": f"{LEP} AND {VG} AND {HORM} AND {EXCLUDE}",
    },
]

# ================= 状态读写 =================

def load_state(state_file: str = STATE_FILE) -> Dict:
    if not os.path.exists(state_file):
        return {"last_run": None, "topics": {}}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error("读取 %s 失败，将重新开始：%s", state_file, e)
        return {"last_run": None, "topics": {}}


def save_state(state: Dict, state_file: str = STATE_FILE) -> None:
    state["last_run"] = datetime.now().isoformat()
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error("写入 %s 失败：%s", state_file, e)

# ================= PubMed 检索 & 摘要 =================

def esearch_pubmed(term: str, days_back: int, retmax: int) -> List[str]:
    """在 PubMed 中检索，返回 PMID 列表"""
    params = {
        "db": "pubmed",
        "retmode": "json",
        "retmax": retmax,
        "term": term,
        "reldate": days_back,
        "datetype": "pdat",
    }
    try:
        r = SESSION.get(ESEARCH_URL, params=params, timeout=60, verify=False, proxies={"http": None, "https": None})
        r.raise_for_status()
        data = r.json()
        idlist = data.get("esearchresult", {}).get("idlist", [])
        return idlist
    except requests.exceptions.RequestException as e:
        logging.error("PubMed 检索失败: %s", e)
        return []


def fetch_pubmed_summaries(pmids: List[str]) -> Dict[str, Dict]:
    """批量获取 PubMed ESummary"""
    if not pmids:
        return {}
    params = {
        "db": "pubmed",
        "retmode": "json",
        "id": ",".join(pmids),
    }
    try:
        r = SESSION.get(ESUMMARY_URL, params=params, timeout=60, verify=False, proxies={"http": None, "https": None})
        r.raise_for_status()
        data = r.json().get("result", {})
        summaries = {}
        for uid in data.get("uids", []):
            summaries[uid] = data.get(uid, {})
        return summaries
    except requests.exceptions.RequestException as e:
        logging.error("获取 PubMed 摘要失败: %s", e)
        return {}

# ================= Zotero 写入 =================

def make_zotero_item(pmid: str, summary: Dict, topic_name: str, collection_key: str) -> Dict:
    title = summary.get("title", f"PMID {pmid}")
    journal = summary.get("fulljournalname", "")
    pubdate = summary.get("pubdate", "")
    volume = summary.get("volume", "")
    issue = summary.get("issue", "")
    pages = summary.get("pages", "")

    item = {
        "itemType": "journalArticle",
        "title": title,
        "creators": [],
        "abstractNote": "",
        "publicationTitle": journal,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "date": pubdate,
        "series": "",
        "seriesTitle": "",
        "seriesText": "",
        "journalAbbreviation": "",
        "language": "",
        "DOI": "",
        "ISSN": "",
        "shortTitle": "",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "accessDate": "",
        "archive": "",
        "archiveLocation": "",
        "libraryCatalog": "PubMed",
        "callNumber": "",
        "rights": "",
        "extra": f"PMID: {pmid}",
        "tags": [
            {"tag": "auto:pubmed"},
            {"tag": f"topic:{topic_name}"},
        ],
        "collections": [],
        "relations": {},
    }
    return item


def push_to_zotero(items: List[Dict], dry_run: bool = False) -> int:
    if not items:
        return 0

    if dry_run:
        logging.info("  [预览模式] 将写入 %d 条目到 Zotero（未实际执行）", len(items))
        return len(items)

    if not ZOTERO_USER_ID or not ZOTERO_API_KEY:
        logging.error("未配置 ZOTERO_USER_ID 或 ZOTERO_API_KEY 环境变量")
        return 0

    zotero_items_url = f"https://api.zotero.org/users/{ZOTERO_USER_ID}/items"
    headers = {
        "Zotero-API-Key": ZOTERO_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        r = SESSION.post(zotero_items_url, headers=headers, data=json.dumps(items), timeout=60, verify=False, proxies={"http": None, "https": None})
        if r.status_code in (200, 201):
            logging.info("成功写入 %d 条目到 Zotero", len(items))
            return len(items)
        else:
            logging.error("写入 Zotero 失败，HTTP %s: %s", r.status_code, r.text[:500])
            return 0
    except requests.exceptions.Timeout:
        logging.error("写入 Zotero 超时")
        return 0
    except requests.exceptions.RequestException as e:
        logging.error("写入 Zotero 请求失败: %s", e)
        return 0

# ================= 单个 TOPIC 处理 =================

def process_topic(topic: Dict, state: Dict, days_back: int, retmax: int, dry_run: bool = False) -> Tuple[int, int, int]:
    name = topic["name"]
    collection = topic["collection"]
    query = topic["query"]

    topic_state = state.setdefault("topics", {}).setdefault(name, {"processed_pmids": []})
    processed: List[str] = topic_state.get("processed_pmids", [])
    processed_set = set(processed)

    logging.info("=== 主题: %s ===", name)
    logging.debug("  Query: %s", query[:100] + "...")

    pmids = esearch_pubmed(query, days_back=days_back, retmax=retmax)
    total_found = len(pmids)
    logging.info("  已记录的 PMID 数: %d", len(processed_set))
    logging.info("  [PubMed] 检索: days_back=%d, retmax=%d", days_back, retmax)
    logging.info("  PubMed 返回 PMID 数: %d", total_found)

    new_pmids = [p for p in pmids if p not in processed_set]
    if not new_pmids:
        logging.info("  没有新的 PMID（都已处理过）")
        return total_found, 0, 0

    logging.info("  本次新的 PMID 数: %d", len(new_pmids))

    summaries = fetch_pubmed_summaries(new_pmids)
    items = []
    for pmid in new_pmids:
        summary = summaries.get(pmid, {})
        items.append(make_zotero_item(pmid, summary, name, collection))

    written = push_to_zotero(items, dry_run=dry_run)

    if written > 0 and not dry_run:
        topic_state["processed_pmids"] = processed + new_pmids
        topic_state["last_update"] = datetime.now().isoformat()
        logging.info("  本次成功写入 Zotero 条目数: %d", written)
    elif dry_run:
        logging.info("  [预览模式] 本次将写入 Zotero 条目数: %d", written)
    else:
        logging.info("  本次没有成功写入 Zotero 条目")

    return total_found, len(new_pmids), written

# ================= 状态查看 =================

def show_status(state: Dict):
    """显示采集状态"""
    print("\n" + "=" * 60)
    print("📊 论文采集状态")
    print("=" * 60)

    last_run = state.get("last_run", "从未运行")
    print(f"\n最后运行时间: {last_run}")

    topics_state = state.get("topics", {})
    if not topics_state:
        print("\n暂无采集记录")
        return

    print(f"\n{'主题名称':<35} {'已采集':<10} {'最后更新':<20}")
    print("-" * 65)

    total_collected = 0
    for topic in TOPICS:
        name = topic["name"]
        topic_data = topics_state.get(name, {})
        count = len(topic_data.get("processed_pmids", []))
        last_update = topic_data.get("last_update", "-")
        if last_update != "-":
            last_update = last_update[:10]  # 只显示日期部分
        print(f"{name:<35} {count:<10} {last_update:<20}")
        total_collected += count

    print("-" * 65)
    print(f"{'总计':<35} {total_collected:<10}")
    print("=" * 60 + "\n")

# ================= 列出主题 =================

def list_topics():
    """列出所有可用主题"""
    print("\n" + "=" * 60)
    print("📋 可用主题列表")
    print("=" * 60)

    for i, topic in enumerate(TOPICS, 1):
        print(f"\n{i}. {topic['name']}")
        print(f"   Collection: {topic['collection']}")

    print("\n" + "=" * 60 + "\n")

# ================= 命令行参数解析 =================

def parse_args():
    parser = argparse.ArgumentParser(
        description='PubMed to Zotero 自动采集工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 使用默认配置运行
  %(prog)s --days 7                 # 检索最近 7 天的论文
  %(prog)s --topic PMC_Vg_Hormone_Lep  # 只处理指定主题
  %(prog)s --dry-run                # 预览模式，不实际写入
  %(prog)s --status                 # 查看采集状态
  %(prog)s --list-topics            # 列出所有主题
        """
    )

    parser.add_argument('--days', type=int, default=DEFAULT_DAYS_BACK,
                        help=f'检索最近多少天的论文 (默认: {DEFAULT_DAYS_BACK})')
    parser.add_argument('--retmax', type=int, default=DEFAULT_RETMAX,
                        help=f'每个主题最多检索多少条 (默认: {DEFAULT_RETMAX})')
    parser.add_argument('--topic', type=str, metavar='NAME',
                        help='只处理指定的主题')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览模式，不实际写入 Zotero')
    parser.add_argument('--status', action='store_true',
                        help='显示采集状态')
    parser.add_argument('--list-topics', action='store_true',
                        help='列出所有可用主题')
    parser.add_argument('--output', type=str, metavar='FILE',
                        help='输出结果到 JSON 文件')
    parser.add_argument('--state-file', type=str, default=STATE_FILE,
                        help=f'状态文件路径 (默认: {STATE_FILE})')
    parser.add_argument('--log-file', type=str, metavar='FILE',
                        help='日志输出到文件')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细日志')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    return parser.parse_args()

# ================= 主程序 =================

def main():
    args = parse_args()

    # 设置日志
    logger = setup_logging(log_file=args.log_file, verbose=args.verbose)

    # 加载状态
    state = load_state(args.state_file)

    # 处理特殊命令
    if args.status:
        show_status(state)
        return 0

    if args.list_topics:
        list_topics()
        return 0

    # 检查环境变量
    if not args.dry_run and (not ZOTERO_USER_ID or not ZOTERO_API_KEY):
        logger.warning("⚠ 未检测到 ZOTERO_USER_ID / ZOTERO_API_KEY 环境变量")
        logger.warning("  请设置环境变量或使用 --dry-run 预览模式")

    # 确定要处理的主题
    topics_to_process = TOPICS
    if args.topic:
        topics_to_process = [t for t in TOPICS if t["name"] == args.topic]
        if not topics_to_process:
            logger.error("未找到主题: %s", args.topic)
            logger.info("使用 --list-topics 查看所有可用主题")
            return 1

    # 开始采集
    logger.info("=" * 60)
    logger.info("🚀 自动 PubMed -> Zotero 采集开始")
    logger.info("=" * 60)
    logger.info("配置: days=%d, retmax=%d, dry_run=%s", args.days, args.retmax, args.dry_run)
    logger.info("处理主题数: %d", len(topics_to_process))

    # 采集结果统计
    results = {
        "run_time": datetime.now().isoformat(),
        "config": {
            "days": args.days,
            "retmax": args.retmax,
            "dry_run": args.dry_run,
        },
        "topics": [],
        "summary": {
            "total_found": 0,
            "total_new": 0,
            "total_written": 0,
        }
    }

    for topic in topics_to_process:
        total, new_n, written = process_topic(
            topic, state,
            days_back=args.days,
            retmax=args.retmax,
            dry_run=args.dry_run
        )

        results["topics"].append({
            "name": topic["name"],
            "found": total,
            "new": new_n,
            "written": written,
        })
        results["summary"]["total_found"] += total
        results["summary"]["total_new"] += new_n
        results["summary"]["total_written"] += written

        logger.info("%s: 检索=%d, 新的=%d, 写入=%d", topic["name"], total, new_n, written)

    # 保存状态
    if not args.dry_run:
        save_state(state, args.state_file)
        logger.info("状态已保存到 %s", args.state_file)

    # 输出结果
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info("结果已输出到 %s", args.output)

    # 打印总结
    logger.info("=" * 60)
    logger.info("📊 采集完成")
    logger.info("  总检索: %d", results["summary"]["total_found"])
    logger.info("  新论文: %d", results["summary"]["total_new"])
    logger.info("  已写入: %d", results["summary"]["total_written"])
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
