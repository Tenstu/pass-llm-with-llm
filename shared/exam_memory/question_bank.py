"""question_bank.py — 题库 CRUD + LLM 生成管道（Phase 2.1）。

对齐 exam-memory V2 设计：
  - 文件格式：YAML frontmatter + Markdown body（与 experiences/ 平行）
  - 检索层：复用 hybrid_search，不独立建索引
  - 零强制依赖：LLM 生成可选（litellm），骨架可用无依赖

用法:
    from exam_memory.question_bank import QuestionBank
    bank = QuestionBank()
    bank.add_manual(type="算法", knowledge="双指针", title="两数之和",
                    content="...", answer="C", options={...}, explanation="...")
    results = bank.generate(topic="双指针", count=3, q_type="算法")
"""

from __future__ import annotations

from dataclasses import dataclass

import glob
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from exam_memory.difficulty_calibrator import DifficultyCalibrator
from exam_memory.frontmatter import parse_frontmatter as _parse_frontmatter
from exam_memory.frontmatter import body_text as _body

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
BANK_DIR = BASE_DIR / "bank"

# ── 题型映射 ──────────────────────────────────────────────────

TYPE_PREFIX: dict[str, str] = {
    "单选题": "单选题",
    "多选题": "多选题",
    "算法": "算法",
}

DIFFICULTY_OPTIONS = ("简单", "中等", "困难")

# ── 提取模式 ──────────────────────────────────────────────────

MODE_RAG = "rag"        # 从 hybrid_search 检索 chunks 作为上下文
MODE_TEXT = "text"      # 直接使用提供的文本内容作为上下文
MODE_DIRECT = "direct"  # 无上下文，纯知识出题


# ── 文件工具 ──────────────────────────────────────────────────


def _validate_id(question_id: str, base_dir: Path) -> Path:
    """验证 question_id 不含路径穿越。返回安全的 resolved Path。"""
    target = (base_dir / f"{question_id}.md").resolve()
    if not target.is_relative_to(base_dir.resolve()):
        raise ValueError(f"非法 question_id（路径穿越）: {question_id}")
    return target


def _next_seq(prefix: str, bank_dir: Path = BANK_DIR) -> int:
    """扫描 bank/ 目录，返回下一个自增序号。"""
    pattern = str(bank_dir / f"{prefix}_*.md")
    existing = glob.glob(pattern)
    max_n = 0
    for fp in existing:
        m = re.search(r"_(\d{3})(?:_[0-9a-f]{6})?\.md$", fp)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def _build_filename(q_type: str, knowledge: str, bank_dir: Path = BANK_DIR, seq: int | None = None) -> str:
    """构造标准文件名：{type}_{knowledge}_{seq:03d}_{uuid6}.md"""
    prefix = TYPE_PREFIX.get(q_type, q_type)
    if seq is None:
        seq = _next_seq(prefix, bank_dir=bank_dir)
    safe_knowledge = re.sub(r'[^\w一-鿿-]', '_', knowledge).strip("_")
    short_id = uuid.uuid4().hex[:6]
    return f"{prefix}_{safe_knowledge}_{seq:03d}_{short_id}.md"


# ── Logprobs 提取 / 序列化 ─────────────────────────────────────

def _extract_logprobs(resp: Any) -> list[dict[str, Any]] | None:
    """从 litellm 响应提取 token 级 logprobs。

    返回可 JSON 序列化的 list[dict]，每项含 token/logprob/bytes/top_logprobs。
    任何异常降级为 None 并打 warning。
    """
    try:
        choices = getattr(resp, "choices", None)
        if not choices:
            return None
        raw = getattr(choices[0], "logprobs", None)
        if raw is None:
            return None
        content = getattr(raw, "content", None)
        if content is None:
            return None
        result: list[dict[str, Any]] = []
        for entry in content:
            token_info: dict[str, Any] = {"token": getattr(entry, "token", "")}
            lp = getattr(entry, "logprob", None)
            if lp is not None:
                token_info["logprob"] = lp
            raw_bytes = getattr(entry, "bytes", None)
            if raw_bytes is not None:
                token_info["bytes"] = raw_bytes
            tl = getattr(entry, "top_logprobs", None)
            if tl is not None:
                token_info["top_logprobs"] = [
                    {"token": getattr(t, "token", ""), "logprob": getattr(t, "logprob", None)}
                    for t in tl
                ]
            result.append(token_info)
        return result
    except Exception as exc:
        logger.warning("logprobs 提取失败（降级为 None）：%s", exc)
        return None


def _logprobs_to_json(data: list[dict[str, Any]] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False)


def _logprobs_from_json(s: str | None) -> list[dict[str, Any]] | None:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


# ── LLM 生成管道 ──────────────────────────────────────────────

@dataclass(frozen=True)
class LlmCallResult:
    """统一封装出题 LLM 调用结果，避免 pipeline 依赖 str/dict 混合返回。"""

    ok: bool
    content: str = ""
    error: str | None = None
    logprobs: list[dict[str, Any]] | None = None
    model: str | None = None

    @classmethod
    def success(cls, content: str) -> "LlmCallResult":
        return cls(ok=True, content=content)

    @classmethod
    def success_with_logprobs(
        cls, content: str, logprobs: list[dict[str, Any]], model: str | None = None,
    ) -> "LlmCallResult":
        return cls(ok=True, content=content, logprobs=logprobs, model=model)

    @classmethod
    def failure(cls, error: str) -> "LlmCallResult":
        return cls(ok=False, error=error)

class PromptBuilder:
    """构造题库生成 prompt（system + user context + format spec）。"""

    SYSTEM_TEMPLATE = """\
你是算法面试题库出题专家。根据提供的参考资料，生成高质量的考试题目。

要求：
1. 题干清晰，无歧义，答案唯一确定
2. 选项设计有区分度（常见错误选项应反映典型误区）
3. 解析详细，包含解题思路、关键步骤和复杂度分析
4. 严格遵循输出格式"""

    FORMAT_TEMPLATE = """\
对每道题，按以下格式输出（每道题用 --- 分隔）：

---
## 题干
题目描述

### 选项
**A.** 选项A
**B.** 选项B
**C.** 选项C
**D.** 选项D

### 答案
C

### 解析
详细解析
---

数量：{count} 道
题型：{q_type}
知识点：{topic}"""

    def build(
        self,
        chunks: list[dict],
        topic: str,
        q_type: str,
        count: int,
        mode: str = MODE_RAG,
        source_text: str = "",
    ) -> tuple[str, str]:
        """返回 (system_prompt, user_prompt)。

        mode:
          MODE_RAG   — chunks 来自检索，拼接为参考资料（默认，向后兼容）
          MODE_TEXT  — source_text 直接作为上下文，忽略 chunks
          MODE_DIRECT — 无上下文，纯知识出题
        """
        if mode == MODE_TEXT:
            ctx = source_text.strip() if source_text else "（无参考资料，请根据你的知识出题）"
        elif mode == MODE_DIRECT:
            ctx = ""
        else:  # MODE_RAG
            ctx = "\n\n".join(
                f"[参考资料 {i+1}]\n{c.get('text', '')}"
                for i, c in enumerate(chunks[:5])
            ) if chunks else "（无参考资料，请根据你的知识出题）"

        system = self.SYSTEM_TEMPLATE
        if mode == MODE_DIRECT:
            user = (
                f"知识点：{topic}\n\n"
                + self.FORMAT_TEMPLATE.format(count=count, q_type=q_type, topic=topic)
            )
        else:
            user = (
                f"知识点：{topic}\n\n"
                f"参考资料：\n{ctx}\n\n"
                + self.FORMAT_TEMPLATE.format(count=count, q_type=q_type, topic=topic)
            )
        return system, user

class QuestionParser:
    """将 LLM 原始输出解析为结构化题目列表。

    输入格式（每道题用 --- 分隔）：
    ---
    ## <标题>
    题干内容（Markdown，到 ### 选项 前）
    ### 选项
    **A.** ...
    **B.** ...
    **C.** ...
    **D.** ...
    ### 答案
    C
    ### 解析
    详细解析
    ---
    """

    SEP_PATTERN = re.compile(r"^---\s*$", re.MULTILINE)
    ANSWER_PATTERN = re.compile(
        r"^###\s*(?:答案|Answer)\s*\n(.*?)(?=^###\s*(?:解析|Explanation)|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    EXPLANATION_PATTERN = re.compile(
        r"^###\s*(?:解析|Explanation)\s*\n(.*?)(?=^---\s*$|^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    OPTIONS_BLOCK_PATTERN = re.compile(
        r"^###\s*(?:选项|Options)\s*\n(.*?)(?=^###\s*(?:答案|Answer))",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    OPTION_LINE_PATTERN = re.compile(r"^\s*\*\*([A-D])\.\*\*\s*(.+)$", re.MULTILINE)

    def parse(self, raw_output: str) -> list[dict[str, Any]]:
        """解析 LLM 输出，返回 [{stem, options, answer, explanation}, ...] 列表。"""
        blocks = self.SEP_PATTERN.split(raw_output)
        questions: list[dict[str, Any]] = []

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            title_match = re.search(r"^##\s+.+$", block, re.MULTILINE)
            options_match = self.OPTIONS_BLOCK_PATTERN.search(block)

            if options_match:
                stem_start = title_match.end() if title_match else 0
                raw_stem = block[stem_start:options_match.start()].strip()
                stem = re.sub(r"^##\s*.+\n?", "", raw_stem).strip()
            else:
                stem = ""

            options_raw = options_match.group(1) if options_match else ""
            answer = self._extract(block, self.ANSWER_PATTERN)
            explanation = self._extract(block, self.EXPLANATION_PATTERN)

            options = self._parse_options(options_raw)
            if not stem or not answer:
                logger.warning("解析跳过（缺题干或答案）：%s", stem[:30] if stem else "N/A")
                continue

            questions.append({
                "stem": stem,
                "options": options,
                "answer": answer.strip().upper(),
                "explanation": explanation,
            })

        return questions

    def _extract(self, text: str, pattern) -> str:
        m = pattern.search(text)
        return m.group(1).strip() if m else ""

    def _parse_options(self, raw: str) -> dict[str, str]:
        options: dict[str, str] = {}
        for m in self.OPTION_LINE_PATTERN.finditer(raw):
            options[m.group(1)] = m.group(2).strip()
        return options

class QualityValidator:
    """题目质量校验：过滤不合格条目。"""

    def __init__(
        self,
        min_options: int = 4,
        require_single_answer: bool = True,
        require_explanation: bool = True,
    ):
        self.min_options = min_options
        self.require_single_answer = require_single_answer
        self.require_explanation = require_explanation

    def validate(self, questions: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
        """返回 (valid, invalid) 元组。"""
        valid, invalid = [], []
        for q in questions:
            reasons = self._check(q)
            if reasons:
                q["_reject_reason"] = "; ".join(reasons)
                invalid.append(q)
            else:
                valid.append(q)
        return valid, invalid

    def _check(self, q: dict) -> list[str]:
        reasons: list[str] = []
        answer = q.get("answer", "")
        options = q.get("options", {})

        if not q.get("stem"):
            reasons.append("题干为空")
        if len(options) < self.min_options:
            reasons.append(f"选项不足 {self.min_options} 个（实际 {len(options)}）")
        if self.require_single_answer:
            if len(answer) != 1:
                reasons.append(f"答案格式错误：{answer!r}")
            if answer not in "ABCD":
                reasons.append(f"答案超出范围：{answer!r}")
        if self.require_explanation and not q.get("explanation"):
            reasons.append("解析为空")

        return reasons


# ── 审核门控 ──────────────────────────────────────────────────

class ReviewGate:
    """题目审核门控：自动校验 + 人工 approve/reject。

    用法:
        gate = ReviewGate(bank)
        result = gate.review_gate("算法_双指针_001")
        # result = {"decision": "approve"|"reject", "reasons": [...]}
        gate.approve("算法_双指针_001")   # 人工确认通过
        gate.reject("算法_双指针_001")    # 人工拒绝
    """

    def __init__(self, bank: "QuestionBank"):
        self._bank = bank
        self._validator = QualityValidator()

    def review_gate(self, question_id: str) -> dict[str, Any]:
        """自动审核一道题。返回 {"decision": "approve"|"reject", "reasons": [...]}。"""
        item = self._bank.get(question_id)
        if item is None:
            return {"decision": "reject", "reasons": [f"题目不存在：{question_id}"]}

        reasons: list[str] = []

        # 已审核通过的不重复审核
        if item.get("reviewed"):
            return {"decision": "approve", "reasons": ["已审核通过"]}

        # 构造 validator 可检查的 dict
        q_for_check = {
            "stem": item.get("body", ""),
            "options": self._extract_options(item.get("body", "")),
            "answer": item.get("answer", ""),
            "explanation": self._extract_explanation(item.get("body", "")),
        }
        check_reasons = self._validator._check(q_for_check)
        reasons.extend(check_reasons)

        decision = "approve" if not reasons else "reject"
        return {"decision": decision, "reasons": reasons}

    def approve(self, question_id: str) -> bool:
        """人工审核通过：设置 reviewed=True。返回是否成功。"""
        return self._set_reviewed(question_id, True)

    def reject(self, question_id: str) -> bool:
        """人工拒绝：设置 reviewed=False。返回是否成功。"""
        return self._set_reviewed(question_id, False)

    def _set_reviewed(self, question_id: str, reviewed: bool) -> bool:
        """更新 frontmatter 的 reviewed 字段。"""
        target = _validate_id(question_id, self._bank.bank_dir)
        if not target.exists():
            return False
        text = target.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        fm["reviewed"] = reviewed
        body = _body(text)
        doc = QuestionBank._render(fm, body)
        target.write_text(doc, encoding="utf-8")
        return True

    @staticmethod
    def _extract_options(body: str) -> dict[str, str]:
        """从正文中提取选项。"""
        options: dict[str, str] = {}
        for m in re.finditer(r"^\s*\*\*([A-D])\.\*\*\s*(.+)$", body, re.MULTILINE):
            options[m.group(1)] = m.group(2).strip()
        return options

    @staticmethod
    def _extract_explanation(body: str) -> str:
        """从正文中提取解析。"""
        m = re.search(
            r"^###\s*(?:解析|Explanation)\s*\n(.*?)(?=^##\s|\Z)",
            body, re.MULTILINE | re.DOTALL,
        )
        return m.group(1).strip() if m else ""


# ── 主类 ──────────────────────────────────────────────────────

class QuestionBank:
    """题库 CRUD + 生成管道。

    不强制依赖 litellm；generate() 在 litellm 不可用时
    返回原始文本，由调用方处理。
    """

    def __init__(self, bank_dir: str | Path | None = None):
        if bank_dir:
            self.bank_dir = Path(bank_dir)
        else:
            self.bank_dir = BANK_DIR
        self.bank_dir.mkdir(parents=True, exist_ok=True)
        self._parser = QuestionParser()
        self._validator = QualityValidator()
        self._stem_prefix_len = 50  # 去重：题干前 N 字符比对
        self._calibrator = DifficultyCalibrator(self.bank_dir / "difficulty_stats.json")

        # 语义去重索引（惰性初始化）
        self._semantic_available: bool = False
        self._semantic_index: np.ndarray | None = None  # (N, dim) L2 归一化矩阵
        self._semantic_ids: list[str] = []              # 与矩阵行一一对应的 question_id

    # ── 去重 ──────────────────────────────────────────────────

    def check_duplicate(self, stem: str, question_id: str = "", use_semantic: bool = False) -> list[str]:
        """检查是否存在重复题目。返回重复原因列表（空 = 无重复）。

        规则：
        - stem 前缀比对（前 50 字符标准化后完全匹配）
        - question_id 唯一性（如果传入）
        - use_semantic=True 时额外做向量余弦相似度去重（阈值 0.92）
        """
        reasons: list[str] = []
        norm_stem = self._normalize_stem(stem)
        if not norm_stem:
            return reasons

        for fp in self.bank_dir.glob("*.md"):
            item = self._load_file(fp)
            if item is None:
                continue

            # question_id 唯一性
            if question_id and item.get("question_id") == question_id:
                reasons.append(f"question_id 已存在：{question_id}")
                continue

            # stem 前缀比对
            existing_body = item.get("body", "")
            existing_title = _extract_title(existing_body) or ""
            # 从 body 提取 stem（## 标题行后到 ### 之间的内容）
            stem_match = re.search(
                r"^##\s+[^\n]+\n(.*?)(?=^###|\Z)", existing_body,
                re.MULTILINE | re.DOTALL,
            )
            existing_stem_text = stem_match.group(1).strip() if stem_match else existing_title
            norm_existing = self._normalize_stem(existing_stem_text)

            if norm_stem == norm_existing:
                reasons.append(
                    f"题干前缀重复：'{norm_stem[:30]}...' 与 {item.get('question_id', '?')} 相同"
                )

        # 语义相似度去重（opt-in）：与 stem 前缀结果合并
        if use_semantic:
            semantic_hits = self.check_semantic_duplicate(stem)
            for qid in semantic_hits:
                reasons.append(f"语义相似：'{stem[:30]}...' 与 {qid} 相似度 >= 0.92")

        return reasons

    def _normalize_stem(self, stem: str) -> str:
        """标准化题干：去除空白和标点，取前 N 字符。"""
        s = re.sub(r'\s+', '', stem)
        s = re.sub(r'[，。？！、；：""''【】《》（）]', '', s)
        return s[:self._stem_prefix_len]

    # ── 语义去重 ────────────────────────────────────────────────

    def _ensure_semantic_ready(self) -> bool:
        """确保 embedding 可用。返回是否可用。"""
        if self._semantic_available:
            return True
        try:
            from exam_memory.embedding import is_available as _is_avail
            if _is_avail():
                self._semantic_available = True
                return True
        except Exception:
            pass
        self._semantic_available = False
        return False

    def _rebuild_semantic_index(self) -> None:
        """重建语义索引：扫描 bank/ 目录，对所有 .md 文件编码后构建矩阵。"""
        try:
            from exam_memory.embedding import encode_safe
        except ImportError:
            self._semantic_available = False
            return

        vectors: list[np.ndarray] = []
        ids: list[str] = []
        for fp in sorted(self.bank_dir.glob("*.md")):
            item = self._load_file(fp)
            if item is None:
                continue
            qid = item.get("question_id", fp.stem)
            body_text = item.get("body", "")
            vec = encode_safe(body_text)
            if vec is None:
                logger.debug("语义索引跳过（编码失败）：%s", fp.name)
                continue
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                vec = vec / norm
            vectors.append(vec.astype(np.float32))
            ids.append(qid)

        if vectors:
            self._semantic_index = np.stack(vectors)
            self._semantic_ids = ids
        else:
            self._semantic_index = np.empty((0, 0), dtype=np.float32)
            self._semantic_ids = []
        self._semantic_available = True
        logger.debug("语义索引已重建：%d 条", len(ids))

    def _update_semantic_index(self, question_id: str, body_text: str) -> None:
        """增量更新：将新题目的向量追加到索引。"""
        if not self._semantic_available:
            return
        try:
            from exam_memory.embedding import encode_safe
        except ImportError:
            return

        vec = encode_safe(body_text)
        if vec is None:
            return
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        vec = vec.astype(np.float32)

        if self._semantic_index is None or self._semantic_index.size == 0:
            self._semantic_index = vec.reshape(1, -1)
        else:
            if vec.shape[0] != self._semantic_index.shape[1]:
                logger.warning(
                    "语义索引维度不匹配（期望 %d，实际 %d），重建索引",
                    self._semantic_index.shape[1], vec.shape[0],
                )
                self._rebuild_semantic_index()
                return
            self._semantic_index = np.vstack([self._semantic_index, vec.reshape(1, -1)])
        self._semantic_ids.append(question_id)

    def check_semantic_duplicate(
        self, stem: str, threshold: float = 0.92,
    ) -> list[str]:
        """基于向量余弦相似度的语义去重检查。

        Args:
            stem: 待检查的题干文本。
            threshold: 相似度阈值（0~1），默认 0.92。

        Returns:
            重复的 question_id 列表（相似度 >= threshold）。
        """
        if not self._ensure_semantic_ready():
            return []

        # 惰性构建索引
        if self._semantic_index is None or self._semantic_index.size == 0:
            self._rebuild_semantic_index()

        if self._semantic_index is None or self._semantic_index.size == 0:
            return []

        try:
            from exam_memory.embedding import encode_safe
        except ImportError:
            return []

        q_vec = encode_safe(stem)
        if q_vec is None:
            return []

        # 确保 L2 归一化
        norm = float(np.linalg.norm(q_vec))
        if norm > 0:
            q_vec = q_vec / norm
        q_vec = q_vec.astype(np.float32)

        # 维度对齐
        if q_vec.shape[0] != self._semantic_index.shape[1]:
            logger.warning(
                "语义去重维度不匹配（期望 %d，实际 %d），重建索引",
                self._semantic_index.shape[1], q_vec.shape[0],
            )
            self._rebuild_semantic_index()
            if self._semantic_index is None or self._semantic_index.size == 0:
                return []
            if q_vec.shape[0] != self._semantic_index.shape[1]:
                return []

        # 余弦相似度 = L2 归一化后的点积
        scores = (self._semantic_index @ q_vec.reshape(-1, 1)).flatten()

        hits: list[str] = []
        for i, score in enumerate(scores):
            if score >= threshold and i < len(self._semantic_ids):
                hits.append(self._semantic_ids[i])
        return hits

    # ── CRUD ────────────────────────────────────────────────

    def add_manual(
        self,
        title: str,
        content: str,
        q_type: str,
        knowledge: str,
        answer: str,
        options: dict[str, str] | None = None,
        explanation: str = "",
        difficulty: str = "中等",
        source: str = "manual",
        source_url: str = "",
        tags: list[str] | None = None,
        reviewed: bool = False,
        generated: bool = False,
        check_dup: bool = False,
        calibrate_difficulty: bool = False,
        logprobs_data: list[dict[str, Any]] | None = None,
    ) -> str:
        """人工录入一道题。返回写入的文件名。

        check_dup: True 时检查 stem 前缀重复（默认 False，保持向后兼容）。
        calibrate_difficulty: True 时根据答题历史校准难度标记（默认 False）。
        logprobs_data: 蒸馏侧信道数据；如有则写入同名 .distill.jsonl。
        """
        if q_type not in TYPE_PREFIX:
            raise ValueError(f"不支持的题型：{q_type}（支持：{list(TYPE_PREFIX)}）")
        if difficulty not in DIFFICULTY_OPTIONS:
            raise ValueError(f"不支持的难度：{difficulty}（支持：{DIFFICULTY_OPTIONS}）")

        # 难度校准（opt-in）
        original_difficulty = difficulty
        if calibrate_difficulty:
            calibrated = self._calibrator.calibrate(knowledge, difficulty)
            if calibrated != difficulty:
                difficulty = calibrated

        # 去重检查（opt-in）
        if check_dup:
            dup_reasons = self.check_duplicate(content)
            # 语义去重补充（仅当精确去重未命中时）
            if not dup_reasons and self._semantic_available:
                semantic_hits = self.check_semantic_duplicate(content)
                if semantic_hits:
                    dup_reasons = [f"语义重复：{'; '.join(semantic_hits)}"]
            if dup_reasons:
                raise ValueError(f"题目重复：{'; '.join(dup_reasons)}")

        filename = _build_filename(q_type, knowledge, bank_dir=self.bank_dir)
        filepath = self.bank_dir / filename

        today = _today()
        fm: dict[str, Any] = {
            "type": q_type,
            "knowledge": knowledge,
            "difficulty": difficulty,
            "source": source,
            "generated": generated,
            "reviewed": reviewed,
            "question_id": filename.replace(".md", ""),
            "tags": tags or [],
            "created": today,
        }
        if calibrate_difficulty and difficulty != original_difficulty:
            fm["difficulty_suggested"] = original_difficulty
        if source_url:
            fm["source_url"] = source_url

        options = options or {}
        option_lines = "\n".join(
            f"**{k}.** {v}" for k, v in sorted(options.items())
        )

        body = (
            f"## {title}\n\n"
            f"{content}\n\n"
            f"### 选项\n\n{option_lines}\n\n"
            f"### 答案\n\n{answer}\n\n"
            f"### 解析\n\n{explanation}\n"
        )

        doc = self._render(fm, body)
        filepath.write_text(doc, encoding="utf-8")

        # 增量更新语义索引（仅在已就绪时，不触发惰性初始化）
        if self._semantic_available and self._semantic_index is not None:
            self._update_semantic_index(
                fm.get("question_id", filename.replace(".md", "")), body,
            )

        # 蒸馏侧信道
        if logprobs_data is not None:
            sidecar_path = filepath.with_suffix(".distill.jsonl")
            record = {
                "question_id": fm.get("question_id", filename.replace(".md", "")),
                "stem": content,
                "options": options or {},
                "answer": answer,
                "logprobs": logprobs_data,
                "model": None,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            sidecar_path.write_text(
                json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            logger.debug("蒸馏侧信道已写入: %s", sidecar_path.name)

        logger.info("已保存题目: %s", filename)
        return filename

    def add(self, question: dict, check_dup: bool = True, calibrate_difficulty: bool = False) -> str:
        """从 dict 保存一道题。

        支持两种输入格式：
        - 完整格式（add_manual 调用方）: title, content, type, knowledge, answer, ...
        - 解析器格式（generate 管道）: stem, options, answer, explanation, type, knowledge

        check_dup: 默认 True，自动检查 stem 重复。管道调用时启用。
        calibrate_difficulty: 默认 False，是否根据历史校准难度。
        """
        if "stem" in question:
            return self.add_manual(
                title=question.get("stem", "未命名题目")[:50],
                content=question["stem"],
                q_type=question["type"],
                knowledge=question["knowledge"],
                answer=question["answer"],
                options=question.get("options"),
                explanation=question.get("explanation", ""),
                difficulty=question.get("difficulty", "中等"),
                source=question.get("source", "llm"),
                source_url=question.get("source_url", ""),
                tags=question.get("tags", []),
                reviewed=False,
                generated=True,
                check_dup=check_dup,
                calibrate_difficulty=calibrate_difficulty,
                logprobs_data=question.get("_logprobs"),
            )
        return self.add_manual(
            title=question["title"],
            content=question["content"],
            q_type=question["type"],
            knowledge=question["knowledge"],
            answer=question["answer"],
            options=question.get("options"),
            explanation=question.get("explanation", ""),
            difficulty=question.get("difficulty", "中等"),
            source=question.get("source", "llm"),
            source_url=question.get("source_url", ""),
            tags=question.get("tags", []),
            reviewed=False,
            check_dup=check_dup,
            calibrate_difficulty=calibrate_difficulty,
            logprobs_data=question.get("_logprobs"),
        )

    def get(self, question_id: str) -> dict | None:
        """按 question_id 读取题目。"""
        target = _validate_id(question_id, self.bank_dir)
        if not target.exists():
            return None
        return self._load_file(target)

    def list_all(
        self,
        q_type: str | None = None,
        knowledge: str | None = None,
    ) -> list[dict]:
        """列出题库，支持题型/知识点过滤。"""
        results: list[dict] = []
        for fp in sorted(self.bank_dir.glob("*.md")):
            item = self._load_file(fp)
            if q_type and item.get("type") != q_type:
                continue
            if knowledge and item.get("knowledge") != knowledge:
                continue
            results.append(item)
        return results

    def delete(self, question_id: str) -> bool:
        """删除题目。返回是否成功。"""
        target = _validate_id(question_id, self.bank_dir)
        if not target.exists():
            return False
        target.unlink()
        logger.info("已删除: %s", question_id)
        return True

    def count(self, q_type: str | None = None) -> int:
        """统计题目数（可过滤题型）。"""
        if q_type:
            return len(self.list_all(q_type=q_type))
        return len(list(self.bank_dir.glob("*.md")))

    # ── 生成管道 ────────────────────────────────────────────

    def generate(
        self,
        topic: str,
        count: int = 3,
        q_type: str = "算法",
        difficulty: str = "中等",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """RAG + LLM 生成题目管道（向后兼容入口）。

        等价于 rag_extract()。保留用于已有调用方。
        """
        return self.rag_extract(topic, count, q_type, difficulty, top_k)

    def rag_extract(
        self,
        topic: str,
        count: int = 3,
        q_type: str = "算法",
        difficulty: str = "中等",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """RAG 模式：hybrid_search 检索 → prompt → LLM → 解析 → 校验 → 保存。"""
        chunks = self._retrieve(topic, q_type, top_k)
        system_prompt, user_prompt = PromptBuilder().build(
            chunks, topic, q_type, count, mode=MODE_RAG,
        )
        return self._run_pipeline(system_prompt, user_prompt, topic, q_type, difficulty)

    def text_extract(
        self,
        source_text: str,
        topic: str,
        count: int = 3,
        q_type: str = "算法",
        difficulty: str = "中等",
    ) -> dict[str, Any]:
        """文本模式：直接使用提供的文本内容作为上下文出题。"""
        system_prompt, user_prompt = PromptBuilder().build(
            [], topic, q_type, count,
            mode=MODE_TEXT, source_text=source_text,
        )
        return self._run_pipeline(system_prompt, user_prompt, topic, q_type, difficulty)

    def direct_extract(
        self,
        topic: str,
        count: int = 3,
        q_type: str = "算法",
        difficulty: str = "中等",
    ) -> dict[str, Any]:
        """直出模式：无上下文，纯靠 LLM 知识出题。"""
        system_prompt, user_prompt = PromptBuilder().build(
            [], topic, q_type, count, mode=MODE_DIRECT,
        )
        return self._run_pipeline(system_prompt, user_prompt, topic, q_type, difficulty)

    def _run_pipeline(
        self,
        system_prompt: str,
        user_prompt: str,
        topic: str,
        q_type: str,
        difficulty: str,
    ) -> dict[str, Any]:
        """共享管道：call_llm → parse → validate → save。"""
        capture_logprobs = os.environ.get("EXAM_MEMORY_CAPTURE_LOGPROBS", "0") == "1"
        result: dict[str, Any] = {
            "saved": [],
            "validated": [],
            "rejected": [],
            "raw_llm_output": None,
            "error": None,
            "logprobs_captured": False,
        }

        llm_result = self._call_llm(system_prompt, user_prompt, capture_logprobs=capture_logprobs)
        if not llm_result.ok:
            result["error"] = llm_result.error or "LLM 调用失败"
            return result

        raw = llm_result.content
        if not raw:
            result["error"] = "LLM 不可用：未返回题目内容"
            return result
        result["raw_llm_output"] = raw

        if llm_result.logprobs is not None:
            result["logprobs_captured"] = True

        questions = self._parser.parse(raw)
        if not questions:
            result["error"] = "LLM 输出未解析出任何题目"
            return result

        valid, rejected = self._validator.validate(questions)
        result["rejected"] = rejected

        for q in valid:
            q["type"] = q_type
            q["knowledge"] = topic
            q["difficulty"] = difficulty
            if llm_result.logprobs is not None:
                q["_logprobs"] = llm_result.logprobs
            try:
                fname = self.add(q)
            except ValueError as e:
                q["_reject_reason"] = str(e)
                result["rejected"].append(q)
                continue
            result["saved"].append(fname)
            loaded = self._load_file(self.bank_dir / fname)
            if loaded:
                result["validated"].append(loaded)

        return result

    # ── 检索 ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 5,
        q_type: str | None = None,
    ) -> list[dict]:
        """复用 hybrid_search 搜索题库（不独立建索引）。

        扫描 bank/ 的 frontmatter 做过滤，返回完整题目内容。
        """
        try:
            from exam_memory.hybrid_search import hybrid_search
            from exam_memory.fts_store import FTSStore
            from exam_memory.vector_store import NumpyVectorStore

            fts = FTSStore()
            vec = NumpyVectorStore()
            hits = hybrid_search(
                query, fts, vec, limit=limit, exp_type=q_type, source_filter="bank"
            )
            fts.close()
        except Exception as e:
            logger.debug("hybrid_search 失败，降级为全文扫描：%s", e)
            hits = []

        if not hits:
            return self._fallback_search(query, limit, q_type)

        results: list[dict] = []
        for hit in hits:
            text = hit.get("text", "")
            meta = hit.get("metadata", {})
            canonical_key = hit.get("canonical_key", meta.get("canonical_key", ""))
            file_name = meta.get("file_name", "")
            source_dir = meta.get("source_dir", "")
            if not file_name and "/" in canonical_key:
                source_dir, file_name = canonical_key.split("/", 1)
            if source_dir and source_dir != "bank":
                continue
            if canonical_key and "/" in canonical_key and not canonical_key.startswith("bank/"):
                continue
            qid = file_name.replace(".md", "")
            if canonical_key.startswith("bank/") or source_dir == "bank":
                qid = qid or canonical_key.removeprefix("bank/").replace(".md", "")
            if qid:
                full = self.get(qid)
                if full:
                    results.append(full)
                    continue
            results.append({
                "question_id": qid or "",
                "title": meta.get("title", ""),
                "text": text,
                "score": hit.get("score"),
            })
        return results

    def import_from_dir(self, path: str | Path) -> int:
        """批量导入 Markdown 题库文件到 bank/。返回导入条数。"""
        src = Path(path).resolve()
        if not src.is_dir():
            raise ValueError(f"目录不存在：{path}")
        bank_root = self.bank_dir.resolve()
        if not src.is_relative_to(bank_root):
            raise ValueError(f"导入路径超出题库目录: {path}")

        # 建立已有文件的索引: (type, knowledge) -> filename
        existing: set[tuple[str, str]] = set()
        for fp in self.bank_dir.glob("*.md"):
            text = fp.read_text(encoding="utf-8")
            em = _parse_frontmatter(text)
            existing.add((em.get("type", ""), em.get("knowledge", "")))

        imported = 0
        for fp in sorted(src.glob("*.md")):
            text = fp.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)
            body = _body(text)

            q_type = fm.get("type", "")
            if q_type not in TYPE_PREFIX:
                logger.warning("跳过（未知题型 %s）：%s", q_type, fp.name)
                continue

            knowledge = fm.get("knowledge", "未分类")
            if (q_type, knowledge) in existing:
                logger.debug("已存在（%s / %s），跳过", q_type, knowledge)
                continue

            filename = _build_filename(q_type, knowledge, bank_dir=self.bank_dir)
            fm.setdefault("question_id", filename.replace(".md", ""))
            fm.setdefault("imported", True)
            fm.setdefault("source", fm.get("source", fp.name))

            doc = self._render(fm, body)
            (self.bank_dir / filename).write_text(doc, encoding="utf-8")
            existing.add((q_type, knowledge))
            imported += 1

        logger.info("导入完成：%d 条 -> %s", imported, self.bank_dir)
        return imported

    # ── 内部方法 ─────────────────────────────────────────────

    def _retrieve(self, topic: str, q_type: str, top_k: int) -> list[dict]:
        """从 experiences/ + bank/ 检索相关 chunks。"""
        try:
            from exam_memory.hybrid_search import hybrid_search
            from exam_memory.fts_store import FTSStore
            from exam_memory.vector_store import NumpyVectorStore

            fts = FTSStore()
            vec = NumpyVectorStore()
            hits = hybrid_search(topic, fts, vec, limit=top_k, exp_type=q_type)
            fts.close()
            return hits
        except Exception as e:
            logger.debug("检索失败：%s", e)
            return []

    def _call_llm(self, system: str, user: str, capture_logprobs: bool = False) -> LlmCallResult:
        """调用配置的出题 LLM；失败返回 pipeline 可消费的结果对象。"""
        model = os.environ.get("EXAM_MEMORY_LLM_MODEL", "").strip()
        if not model:
            return LlmCallResult.failure("LLM 不可用：未配置 EXAM_MEMORY_LLM_MODEL")

        try:
            from litellm import completion
        except ImportError:
            logger.info("litellm 未安装，跳过 LLM 调用（pip install '.[generate]'）")
            return LlmCallResult.failure("LLM 不可用：litellm 未安装")

        try:
            call_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            }
            logprobs_data: list[dict[str, Any]] | None = None
            if capture_logprobs:
                top_k = int(os.environ.get("EXAM_MEMORY_LOGPROBS_TOP_K", "5"))
                call_kwargs["logprobs"] = True
                call_kwargs["top_logprobs"] = top_k
            resp = completion(**call_kwargs)
            content = resp.choices[0].message.content or ""
            if capture_logprobs:
                logprobs_data = _extract_logprobs(resp)
                if logprobs_data is None:
                    logger.warning("logprobs 捕获未成功（provider 可能不支持），降级为纯文本")
                return LlmCallResult.success_with_logprobs(content, logprobs_data, model=model)
            return LlmCallResult.success(content)
        except Exception as e:
            logger.error("LLM 调用失败：%s", e)
            return LlmCallResult.failure(f"LLM 调用失败：{e}")

    def _fallback_search(
        self, query: str, limit: int, q_type: str | None
    ) -> list[dict]:
        """hybrid_search 不可用时的降级：全文扫描 + 简单关键词匹配。"""
        results: list[dict] = []
        q_lower = query.lower()
        for fp in sorted(self.bank_dir.glob("*.md")):
            if len(results) >= limit:
                break
            item = self._load_file(fp)
            if q_type and item.get("type") != q_type:
                continue
            text_blob = f"{item.get('title','')} {item.get('body','')}".lower()
            if q_lower in text_blob or not q_lower:
                results.append(item)
        return results

    def _load_file(self, fp: Path) -> dict | None:
        """读取 .md 文件，返回含 frontmatter + body + raw 的 dict。"""
        text = fp.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        body = _body(text)
        answer_match = re.search(r"^###\s*答案\s*\n(.+?)(?:\n\n|\Z)", body, re.MULTILINE)
        return {
            "question_id": fm.get("question_id", fp.stem),
            "file_name": fp.name,
            "type": fm.get("type", ""),
            "knowledge": fm.get("knowledge", ""),
            "difficulty": fm.get("difficulty", "中等"),
            "source": fm.get("source", ""),
            "source_url": fm.get("source_url", ""),
            "generated": fm.get("generated", False),
            "reviewed": fm.get("reviewed", False),
            "tags": fm.get("tags", []),
            "created": fm.get("created", ""),
            "title": _extract_title(text) or fm.get("knowledge", fp.stem),
            "body": body,
            "answer": answer_match.group(1).strip() if answer_match else "",
            "raw": text,
        }

    @staticmethod
    def _render(fm: dict, body: str) -> str:
        yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False)
        return f"---\n{yaml_str}---\n\n{body}"


# ── 辅助函数 ──────────────────────────────────────────────────

def _extract_title(text: str) -> str | None:
    """提取正文第一个 ## 标题。"""
    m = re.search(r"^##\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _today() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")
