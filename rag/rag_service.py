import re

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from utils.path_tool import get_abs_path


NO_ENOUGH_RAG_RESULT = "知识库中未检索到足够资料。"

FAULT_TERMS = [
    "故障", "排查", "维修", "异常", "漏扫", "不充电", "充不上电", "无法充电",
    "异响", "噪音", "拖布不出水", "不出水", "无法回充", "回充失败", "找不到基站",
    "扫不干净", "报错", "错误码", "传感器", "卡住",
]
MAINTENANCE_TERMS = [
    "维护", "保养", "清洁", "清理", "耗材", "主刷", "边刷", "滤网", "拖布",
    "集尘袋", "尘盒", "更换", "寿命",
]
PURCHASE_TERMS = [
    "选购", "购买", "推荐", "适合", "小户型", "大户型", "地毯", "宠物", "吸力",
    "导航", "避障", "预算", "型号",
]
USAGE_TERMS = [
    "使用", "清扫", "扫拖", "拖地", "建图", "地图", "分区", "禁区", "基站",
    "水箱", "模式", "预约", "覆盖率",
]
GENERIC_TERMS = ["扫地机器人", "扫拖机器人", "扫拖一体", "机器人"]

QUERY_TYPE_RULES = {
    "fault": FAULT_TERMS,
    "maintenance": MAINTENANCE_TERMS,
    "purchase": PURCHASE_TERMS,
    "usage": USAGE_TERMS,
}

SOURCE_HINTS = {
    "fault": ["故障", "排除", "维修"],
    "maintenance": ["维护", "保养"],
    "purchase": ["选购", "指南"],
    "usage": ["100问", "扫地机器人", "扫拖一体"],
}


def print_prompt(prompt):
    print('*'*20)
    print(prompt.to_string())
    print('*' * 20)
    return prompt

class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        return chain

    def retriever_docs(self,query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def _detect_query_type(self, query: str) -> str:
        normalized_query = query.lower()
        for query_type, terms in QUERY_TYPE_RULES.items():
            if any(term.lower() in normalized_query for term in terms):
                return query_type
        return "general"

    def _extract_query_terms(self, query: str) -> list[str]:
        normalized_query = query.lower()
        candidate_terms = (
            FAULT_TERMS
            + MAINTENANCE_TERMS
            + PURCHASE_TERMS
            + USAGE_TERMS
        )
        terms = [term for term in candidate_terms if term.lower() in normalized_query]
        terms.extend(re.findall(r"[a-zA-Z0-9_]{2,}", normalized_query))

        seen_terms = set()
        clean_terms = []
        for term in terms:
            normalized_term = term.strip().lower()
            if not normalized_term or normalized_term in seen_terms:
                continue
            if normalized_term in [item.lower() for item in GENERIC_TERMS]:
                continue
            seen_terms.add(normalized_term)
            clean_terms.append(term)
        return clean_terms

    def _score_doc_relevance(self, doc: Document, query_terms: list[str], query_type: str) -> int:
        source = str(doc.metadata.get("source") or doc.metadata.get("file_path") or "")
        searchable_text = f"{source}\n{doc.page_content}".lower()
        score = 0

        for term in query_terms:
            if term.lower() in searchable_text:
                score += 2

        for hint in SOURCE_HINTS.get(query_type, []):
            if hint.lower() in source.lower():
                score += 2

        if query_type in QUERY_TYPE_RULES:
            for term in QUERY_TYPE_RULES[query_type]:
                if term.lower() in searchable_text:
                    score += 1

        return score

    def _filter_relevant_docs(self, query: str, docs: list[Document]) -> list[Document]:
        query_type = self._detect_query_type(query)
        query_terms = self._extract_query_terms(query)
        scored_docs = []

        for index, doc in enumerate(docs):
            score = self._score_doc_relevance(doc, query_terms, query_type)
            if score <= 0:
                continue
            if query_type == "fault":
                source = str(doc.metadata.get("source") or doc.metadata.get("file_path") or "")
                source_or_content = f"{source}\n{doc.page_content}".lower()
                is_fault_related = any(term.lower() in source_or_content for term in FAULT_TERMS)
                if not is_fault_related:
                    continue
            scored_docs.append((score, index, doc))

        scored_docs.sort(key=lambda item: (-item[0], item[1]))
        return [doc for _, _, doc in scored_docs]

    def _dedupe_docs(self, docs: list[Document]) -> list[Document]:
        deduped_docs = []
        seen_keys = set()
        for doc in docs:
            source = doc.metadata.get("source", "")
            page = doc.metadata.get("page", "")
            content_key = doc.page_content.strip()
            key = (source, page, content_key)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_docs.append(doc)
        return deduped_docs

    def _format_source(self, doc: Document) -> str:
        source = doc.metadata.get("source") or doc.metadata.get("file_path") or "未知来源"
        if isinstance(source, str):
            source = source.replace(get_abs_path(""), "").lstrip("\\/")
        page = doc.metadata.get("page")
        if page is not None:
            return f"{source} 第{page + 1 if isinstance(page, int) else page}页"
        return str(source)

    def _format_sources(self, docs: list[Document]) -> str:
        sources = []
        seen_sources = set()
        for doc in docs:
            source = self._format_source(doc)
            if source in seen_sources:
                continue
            seen_sources.add(source)
            sources.append(source)
        if not sources:
            return "暂无来源信息"
        return "\n".join(f"- {source}" for source in sources)

    def _build_context(self, docs: list[Document]) -> str:
        context = ''
        counter = 0
        for doc in docs:
            counter += 1
            context += f'[参考资料{counter} : 参考资料: {doc.page_content} | 参考元数据: {doc.metadata}\n]'
        return context

    def rag_summarize(self,query: str, with_sources: bool = False) -> str:
        context_docs = self._filter_relevant_docs(
            query,
            self._dedupe_docs(self.retriever_docs(query)),
        )
        if not context_docs:
            if with_sources:
                return f"{NO_ENOUGH_RAG_RESULT}\n\n参考来源：\n- 无"
            return NO_ENOUGH_RAG_RESULT

        context = self._build_context(context_docs)
        answer = self.chain.invoke(
            {
                'input':query,
                'context':context,
            }
        )
        if not with_sources:
            return answer

        return f"{answer}\n\n参考来源：\n{self._format_sources(context_docs)}"

if __name__ == '__main__':
    rag = RagSummarizeService()
    print(rag.rag_summarize('小户型适合哪些扫地机器人'))
