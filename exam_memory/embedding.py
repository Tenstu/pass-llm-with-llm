"""bge-m3 embedding 封装（exam-memory V2 核心层）。

无 LangChain 依赖，CPU-only，静默降级。

用法:
    from exam_memory.embedding import get_embedder, encode, is_available
    if is_available():
        vec = encode("双指针三数之和")          # (1024,) float32
        vecs = encode(["背包问题", "动态规划"])   # (2, 1024) float32
"""

from __future__ import annotations

import os
from typing import Union

import numpy as np

# ── 依赖检测 ────────────────────────────────────────────────

class EmbeddingError(Exception):
    pass


def _check_dependency() -> None:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        raise EmbeddingError(
            "sentence-transformers 未安装。"
            "请运行: pip install '.[embed]'"
        )


# ── 模型单例 ────────────────────────────────────────────────

_MODEL = None


def get_embedder(model_name: str = "BAAI/bge-m3"):
    """延迟加载 bge-m3 模型（单例）。CPU-only。"""
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    _check_dependency()
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

    from sentence_transformers import SentenceTransformer
    _MODEL = SentenceTransformer(model_name, device="cpu")
    return _MODEL


def is_available() -> bool:
    """embedding 层是否可用。"""
    try:
        _check_dependency()
        return True
    except EmbeddingError:
        return False


# ── 编码接口 ────────────────────────────────────────────────

def encode(
    text: Union[str, list[str]],
    *,
    normalize: bool = True,
) -> np.ndarray:
    """将文本编码为 embedding 向量。

    Args:
        text: 单条文本或文本列表。
        normalize: L2 归一化（使 dot product = cosine similarity）。

    Returns:
        float32 numpy 数组，shape (dim,) 或 (n, dim)。
    """
    model = get_embedder()
    emb = model.encode(
        text,
        normalize_embeddings=normalize,
        show_progress_bar=False,
    )
    return np.asarray(emb, dtype=np.float32)


def encode_safe(
    text: Union[str, list[str]],
    *,
    normalize: bool = True,
) -> np.ndarray | None:
    """编码的安静版本——依赖不可用时返回 None。"""
    try:
        return encode(text, normalize=normalize)
    except Exception:
        return None
