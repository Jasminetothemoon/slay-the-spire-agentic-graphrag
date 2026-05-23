import os
import requests
from bs4 import BeautifulSoup
import json

class SlayTheSpireWikiCrawler:
    def __init__(self):
        # 使用官方 MediaWiki API 而不是直接爬取 HTML 页面，完美绕过 Cloudflare 反爬虫 403
        self.api_url = "https://slay-the-spire.fandom.com/api.php"
        self.headers = {"User-Agent": "SlayTheSpireRecommendationEngine/1.0 (https://github.com/example/engine)"}
        
        self.output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw_wiki")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def fetch_page_content(self, page_name: str) -> str:
        """调用 MediaWiki API 获取原生 HTML"""
        print(f"🌍 正在通过 API 请求 Wiki 词条: {page_name}")
        params = {
            "action": "parse",
            "page": page_name,
            "format": "json"
        }
        
        try:
            response = requests.get(self.api_url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                print(f"❌ API 错误: {data['error']['info']}")
                return ""
            # 获取解析后的 HTML 内容
            return data["parse"]["text"]["*"]
        except Exception as e:
            print(f"❌ 页面抓取失败: {e}")
            return ""

    def crawl_strategy_guides(self):
        """爬取猎手的宏观流派攻略"""
        print("\n[Crawler] 开始爬取猎手(Silent)流派攻略文本...")
        # 注意：Wiki上的猎手主条目叫 Silent，其中包含 Strategy 章节
        html = self.fetch_page_content("Silent")
        if not html:
            return
            
        soup = BeautifulSoup(html, "html.parser")
        
        # Fandom Wiki 的词条正文通常包裹在 mw-parser-output 类中
        content_div = soup.find("div", class_="mw-parser-output")
        
        strategies = []
        if content_div:
            # 找到所有的三级标题 (H3)，这通常是流派的名字，比如 "Poison (毒药流)" 或 "Shivs (小刀流)"
            for h3 in content_div.find_all("h3"):
                archetype_name = h3.get_text(strip=True).replace("[edit | edit source]", "").strip()
                
                # 顺着标题往下找，把属于这个流派的所有段落(p标签)收集起来
                paragraphs = []
                sibling = h3.find_next_sibling()
                while sibling and sibling.name not in ["h3", "h2"]: # 遇到下一个大标题就停下
                    if sibling.name == "p":
                        text = sibling.get_text(strip=True)
                        if text:
                            paragraphs.append(text)
                    sibling = sibling.find_next_sibling()
                    
                strategy_text = "\n".join(paragraphs)
                if strategy_text:
                    strategies.append({
                        "class": "Silent",
                        "archetype": archetype_name,
                        "raw_text": strategy_text
                    })
                    
        # 将原始脏数据以 JSON 格式存入硬盘
        output_file = os.path.join(self.output_dir, "strategy_silent.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(strategies, f, ensure_ascii=False, indent=2)
        print(f"✅ 成功保存猎手流派原始攻略至 {output_file}，共抓取到 {len(strategies)} 个战术流派大段文本。")

    def crawl_mechanics(self):
        """
        爬取游戏所有核心机制（Keywords）。
        例如什么是“虚弱(Weak)”，什么是“中毒(Poison)”。
        """
        print("\n[Crawler] 开始爬取全局机制描述词典...")
        html = self.fetch_page_content("Keywords")
        if not html:
            return
            
        soup = BeautifulSoup(html, "html.parser")
        keywords = []
        
        # Fandom 维基通常用表格(article-table)来列出关键字
        tables = soup.find_all("table", class_="article-table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]: # 跳过第一行的表头
                cols = row.find_all("td")
                if len(cols) >= 2:
                    keyword = cols[0].get_text(strip=True)
                    description = cols[1].get_text(strip=True)
                    keywords.append({
                        "mechanic": keyword,
                        "description": description
                    })
                    
        output_file = os.path.join(self.output_dir, "mechanics.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
        print(f"✅ 成功保存机制词汇表至 {output_file}，共解析出 {len(keywords)} 个底层机制。")

if __name__ == "__main__":
    crawler = SlayTheSpireWikiCrawler()
    
    # 执行攻略爬取
    crawler.crawl_strategy_guides()
    # 执行机制爬取
    crawler.crawl_mechanics()
    
    print("\n🎉 【Phase 1: Extract】任务执行完毕。我们已经获得了给大模型阅读的原始素材！")
