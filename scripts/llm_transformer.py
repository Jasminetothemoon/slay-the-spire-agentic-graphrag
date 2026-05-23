import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field

# 如果需要真实调用，请安装 openai 库：pip install openai
# 并在环境变量中设置 OPENAI_API_KEY
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ==========================================
# 1. 定义极其严格的 Pydantic Schema (Graph 结构)
# ==========================================
class SynergyEdge(BaseModel):
    source_entity: str = Field(description="源实体名，例如 'Catalyst' (催化剂)")
    target_entity: str = Field(description="目标实体名，例如 'Poison' (中毒)")
    relation_type: str = Field(description="只能从以下取值：SYNERGY_WITH, CORE_PIECE_FOR, SCALES_WITH, ENHANCES")
    reason: str = Field(description="一句话解释为什么有这个关系，例如 '催化剂能让中毒层数翻倍'")

class ArchetypeGraph(BaseModel):
    archetype_name: str = Field(description="流派的官方/俗称中文名，例如 '毒药流'")
    core_cards: List[str] = Field(description="该流派的核心卡牌中文名列表")
    core_relics: List[str] = Field(description="该流派的核心遗物中文名列表")
    synergies: List[SynergyEdge] = Field(description="流派内实体之间产生的化学反应(连线)")

class LLMTransformer:
    """
    【ETL 管道 - 第 2 步：Transform AI 提炼层】
    负责读取爬取的非结构化英文 Wiki 文本，
    利用大模型的语义理解，强制转化为符合 Neo4j Schema 的强类型图谱数据 (JSON)。
    """
    def __init__(self):
        self.input_file = os.path.join(os.path.dirname(__file__), "..", "data", "raw_wiki", "strategy_silent.json")
        self.output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "processed_graph")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if self.api_key and OpenAI:
            # 严格遵守官方文档：接入 DeepSeek 的 base_url
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        else:
            self.client = None

    def transform_text_to_graph(self, raw_text: str) -> dict:
        """调用大模型，将脏文本转化为 ArchetypeGraph"""
        system_prompt = """
        你是一个精通《杀戮尖塔》的高级游戏数据架构师。
        你需要阅读一段玩家攻略的原始文本，并将其提炼为极其严格的知识图谱数据。
        
        规则：
        1. 必须识别出流派(Archetype)的名称。
        2. 提取出提及的核心卡牌(Cards)和遗物(Relics)，并【尽可能翻译为官方中文名】。
        3. 提取实体间的协同关系(Synergy Edge)，关系类型只能是：SYNERGY_WITH, CORE_PIECE_FOR, SCALES_WITH, ENHANCES。
        4. 你的输出必须完全符合我提供的 JSON Schema。
        """

        if not self.client:
            raise ValueError(
                "❌ 致命错误：未配置 DEEPSEEK_API_KEY！\n"
                "企业级 ETL 管道坚决抵制编造假数据。请您在系统中配置 DeepSeek API 密钥。\n"
                "配置方法（以命令行/终端为例）：\n"
                "Windows: $env:DEEPSEEK_API_KEY=\"您的密钥\"\n"
                "Mac/Linux: export DEEPSEEK_API_KEY=\"您的密钥\""
            )

        # 动态将 Pydantic Schema 转化为要求注入给 DeepSeek
        schema_dict = ArchetypeGraph.model_json_schema()
        system_prompt += f"\n\n你必须以 JSON 格式输出，并且严格遵循以下 JSON Schema：\n{json.dumps(schema_dict, ensure_ascii=False)}"

        print("🤖 正在呼叫 DeepSeek Pro 模型解析文本逻辑...")
        response = self.client.chat.completions.create(
            model="deepseek-pro", # 严格指定使用 PRO 模型
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请提炼以下攻略：\n\n{raw_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        # 获取大模型输出的 JSON 字符串，并使用 Pydantic 严格校验后返回
        raw_json_str = response.choices[0].message.content
        validated_data = ArchetypeGraph.model_validate_json(raw_json_str)
        return validated_data.model_dump()

    def run_pipeline(self):
        print("[Transformer] 开始执行知识图谱结构化清洗...")
        
        if not os.path.exists(self.input_file):
            print(f"❌ 找不到输入文件：{self.input_file}，请先运行 crawler.py")
            return

        with open(self.input_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        processed_archetypes = []
        
        for item in raw_data:
            print(f"\n🔄 正在提炼流派区块：{item.get('archetype', 'Unknown')}")
            # 只取前 1000 字符防止 Token 爆炸
            raw_text = item.get("raw_text", "")[:1000]
            
            graph_data = self.transform_text_to_graph(raw_text)
            
            # 补全元数据
            graph_data["class"] = item.get("class", "Unknown")
            processed_archetypes.append(graph_data)
            print(f"✅ 成功提炼图谱节点: {graph_data['archetype_name']} | 包含 {len(graph_data['synergies'])} 条深度关系链")

        output_file = os.path.join(self.output_dir, "archetypes_graph.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(processed_archetypes, f, ensure_ascii=False, indent=2)
            
        print(f"\n🎉 【Phase 2: Transform】执行完毕！高度结构化的图谱数据已存入 {output_file}")

if __name__ == "__main__":
    transformer = LLMTransformer()
    transformer.run_pipeline()
