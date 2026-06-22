"""NumpyVectorStore — 基于 numpy 的向量存储（exam-memory V2 核心层）。

文件布局 (exam_memory/vectorstore/):
    embeddings.npy   — float32 (N, 1024) 行优先矩阵
    metadata.json    — list[dict]，每条与 embeddings 行一一对应
    manifest.json    — 索引元数据（模型、维度、归一化、schema 版本）

用法:
    from exam_memory.vector_store import NumpyVectorStore, VECTOR_DIR
    store = NumpyVectorStore()
    store.rebuild()                        # 全量重建
    results = store.search("双指针", top_k=3)
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from exam_memory.embedding import encode_safe, EmbeddingError, get_embedding_config
from exam_memory.frontmatter import parse_frontmatter as _parse_frontmatter
from exam_memory.frontmatter import body_text as _extract_text

# ── 路径 ─────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
VECTOR_DIR = BASE_DIR / "vectorstore"
EMB_PATH = VECTOR_DIR / "embeddings.npy"
META_PATH = VECTOR_DIR / "metadata.json"
MANIFEST_PATH = VECTOR_DIR / "manifest.json"
_INDEX_VERSION = 1
_ALLOWED_SOURCE_DIRS = {"experiences", "bank"}

# ── 类型别名 ─────────────────────────────────────────────────

_TextOrMeta = tuple[str, dict[str, Any]]   # (full_text, metadata)

# ── 辅助 ─────────────────────────────────────────────────────

def _load_full_text(filename: str, exp_dir: Path) -> str:
    """按文件名从 experiences/ 加载完整 Markdown。找不到返回空串。"""
    if not filename:
        return ""
    target = exp_dir / filename
    if not target.exists():
        return ""
    try:
        return target.read_text(encoding="utf-8")
    except Exception:
        return ""


def _build_manifest(embs: np.ndarray, meta: list[dict]) -> dict:
    """根据当前 embedding 配置和索引数据构建 manifest。"""
    cfg = get_embedding_config()
    provider = cfg.get("PROVIDER", "local")
    model = cfg.get("API_MODEL") if provider == "api" else cfg.get("MODEL")
    return {
        "embedding_provider": provider,
        "embedding_model": model or "BAAI/bge-m3",
        "embedding_dim": int(embs.shape[1]) if embs.ndim >= 2 else 0,
        "normalize": cfg.get("NORMALIZE", "1") == "1",
        "pooling": "cls",
        "created_at": _now_iso(),
        "source_count": len(meta),
        "index_version": _INDEX_VERSION,
    }


def _write_text_sync(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def _fsync_path(path: Path) -> None:
    with path.open("r+b") as f:
        os.fsync(f.fileno())


def _temp_path_for(path: Path) -> Path:
    suffix = ".tmp.npy" if path.suffix == ".npy" else ".tmp"
    tmp = tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=suffix,
        delete=False,
    )
    tmp_path = Path(tmp.name)
    tmp.close()
    return tmp_path


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_manifest(manifest: dict) -> None:
    """原子写入 manifest.json。"""
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _temp_path_for(MANIFEST_PATH)
    try:
        _write_text_sync(tmp, json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(tmp, MANIFEST_PATH)
    finally:
        if tmp.exists():
            tmp.unlink()


def _read_manifest() -> dict | None:
    """读取 manifest.json，不存在或解析失败返回 None。"""
    if not MANIFEST_PATH.exists():
        return None
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _validate_manifest(manifest: dict, embs: np.ndarray) -> bool:
    """校验 manifest 与当前索引/配置是否一致。"""
    cfg = get_embedding_config()
    expected_provider = cfg.get("PROVIDER", "local")
    expected_model = cfg.get("API_MODEL") if expected_provider == "api" else cfg.get("MODEL")
    expected_model = expected_model or "BAAI/bge-m3"
    expected_dim = int(embs.shape[1]) if embs.ndim >= 2 else 0
    expected_normalize = cfg.get("NORMALIZE", "1") == "1"

    version = manifest.get("index_version", manifest.get("schema_version"))
    try:
        version = int(version)
    except (TypeError, ValueError):
        return False
    if version != _INDEX_VERSION:
        return False
    if manifest.get("embedding_provider", expected_provider) != expected_provider:
        return False
    if manifest.get("embedding_model") != expected_model:
        return False
    if manifest.get("embedding_dim") != expected_dim:
        return False
    normalize = manifest.get("normalize", manifest.get("embedding_normalize"))
    if normalize != expected_normalize:
        return False
    if manifest.get("pooling", "cls") != "cls":
        return False
    return True


def _validate_snapshot(manifest: dict, embs: np.ndarray, meta: Any) -> bool:
    """校验 manifest、向量矩阵和 metadata 是否属于同一个完整快照。"""
    if not isinstance(meta, list):
        return False
    if not isinstance(embs, np.ndarray) or embs.ndim != 2:
        return False
    if len(meta) != int(embs.shape[0]):
        return False

    source_count = manifest.get("source_count", manifest.get("entry_count"))
    if source_count is not None:
        try:
            if int(source_count) != len(meta):
                return False
        except (TypeError, ValueError):
            return False

    if not _validate_manifest(manifest, embs):
        return False

    expected_emb_hash = manifest.get("embeddings_sha256")
    if expected_emb_hash and _file_sha256(EMB_PATH) != expected_emb_hash:
        return False

    expected_meta_hash = manifest.get("metadata_sha256")
    if expected_meta_hash and _file_sha256(META_PATH) != expected_meta_hash:
        return False

    return True


def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _load_markdown_entries(
    source_dirs: tuple[str, ...] = ("experiences",),
    type_filter: str | None = None,
) -> list[_TextOrMeta]:
    """扫描指定 markdown 数据目录，返回 [(body, meta_with_filename), ...]。"""
    items: list[_TextOrMeta] = []
    for source_dir in source_dirs:
        if source_dir not in _ALLOWED_SOURCE_DIRS:
            continue
        data_dir = BASE_DIR / source_dir
        pattern = str(data_dir / "*.md")
        for fp in glob.glob(pattern):
            path = Path(fp)
            if path.name.upper() == "README.MD":
                continue
            text = path.read_text(encoding="utf-8")
            meta = _parse_frontmatter(text)
            if not meta.get("type"):
                continue
            if type_filter and meta.get("type") != type_filter:
                continue
            meta["file_name"] = path.name
            meta["source_dir"] = source_dir
            meta["canonical_key"] = f"{source_dir}/{path.name}"
            body = _extract_text(text)
            items.append((body, meta))
    return items


def _load_experiences(type_filter: str | None = None) -> list[_TextOrMeta]:
    """扫描 experiences/ 目录，返回 [(full_text, meta_with_filename), ...]。"""
    return _load_markdown_entries(("experiences",), type_filter)


def _entry_source_dir(meta: dict[str, Any]) -> Path:
    """返回 metadata 指向的安全数据目录。"""
    source_dir = meta.get("source_dir", "experiences")
    if source_dir not in _ALLOWED_SOURCE_DIRS:
        source_dir = "experiences"
    return BASE_DIR / source_dir


# ── NumpyVectorStore ─────────────────────────────────────────

class NumpyVectorStore:
    """纯 numpy 向量存储，零外部数据库依赖。"""

    def __init__(self):
        self._embs: np.ndarray | None = None   # (N, D) float32
        self._meta: list[dict[str, Any]] = []   # len == N

    # ── 持久化 ──────────────────────────────────────────────

    def save(self) -> None:
        if self._embs is not None and self._meta:
            VECTOR_DIR.mkdir(parents=True, exist_ok=True)
            tmp_paths: list[Path] = []
            tmp_emb = _temp_path_for(EMB_PATH)
            tmp_meta = _temp_path_for(META_PATH)
            tmp_manifest = _temp_path_for(MANIFEST_PATH)
            tmp_paths.extend([tmp_emb, tmp_meta, tmp_manifest])
            try:
                np.save(str(tmp_emb), self._embs)
                _fsync_path(tmp_emb)

                _write_text_sync(
                    tmp_meta,
                    json.dumps(self._meta, ensure_ascii=False, indent=2),
                )

                manifest = _build_manifest(self._embs, self._meta)
                manifest["embeddings_sha256"] = _file_sha256(tmp_emb)
                manifest["metadata_sha256"] = _file_sha256(tmp_meta)
                _write_text_sync(
                    tmp_manifest,
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )

                os.replace(tmp_emb, EMB_PATH)
                os.replace(tmp_meta, META_PATH)
                os.replace(tmp_manifest, MANIFEST_PATH)
            finally:
                for tmp_path in tmp_paths:
                    if tmp_path.exists():
                        tmp_path.unlink()

    def load(self) -> bool:
        if not EMB_PATH.exists() or not META_PATH.exists():
            return False
        try:
            embs = np.load(str(EMB_PATH))
            meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        except Exception:
            return False
        manifest = _read_manifest()
        if manifest is None or not _validate_snapshot(manifest, embs, meta):
            return False
        self._embs = embs
        self._meta = meta
        return True

    def clear(self) -> None:
        self._embs = None
        self._meta = []
        for p in (EMB_PATH, META_PATH, MANIFEST_PATH):
            if p.exists():
                p.unlink()

    # ── 索引 ────────────────────────────────────────────────

    def rebuild(self, *, verbose: bool = False) -> int:
        """全量重建：扫描 experiences/ + bank/ 并重新向量化。返回入库条数。"""
        items = _load_markdown_entries(("experiences", "bank"))
        texts = [t for t, _ in items]
        metas = [m for _, m in items]

        embeddings = encode_safe(texts)
        if embeddings is None:
            if verbose:
                import warnings
                warnings.warn(
                    "[vector_store] embedding 不可用，将清除已有索引",
                    RuntimeWarning,
                )
            self.clear()
            return 0

        self._embs = embeddings.astype(np.float32)
        self._meta = []
        for i, meta in enumerate(metas):
            meta["id"] = meta.get("file_name", f"{meta.get('type', '?')}_{meta.get('knowledge', '?')}_{i:03d}.md")
            meta.setdefault("source_dir", "experiences")
            meta.setdefault("canonical_key", f"{meta['source_dir']}/{meta['id']}")
            self._meta.append(meta)

        self.save()
        if verbose:
            print(f"[vector_store] 已重建: {len(metas)} 条经验, "
                  f"向量维度 {self._embs.shape}")
        return len(metas)

    # ── 搜索 ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        type_filter: str | None = None,
        source_filter: str | None = None,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """语义搜索。

        Args:
            query: 查询文本。
            top_k: 最多返回条数。
            type_filter: 题型过滤（单选题/多选题/算法），None 不过滤。
            min_score: 最低余弦相似度阈值（0~1）。

        Returns:
            按相似度降序排列的 dict 列表，每条含:
             - score: float cosine similarity
             - text: str 正文
             - metadata: dict
        """
        if self._embs is None or len(self._meta) == 0:
            if not self.load():
                return []

        q_vec = encode_safe(query)
        if q_vec is None or self._embs is None:
            return []

        if q_vec.ndim == 1:
            q_vec = q_vec.reshape(1, -1)

        scores = (self._embs @ q_vec.T).flatten()

        candidates = list(range(len(self._meta)))
        if type_filter:
            candidates = [
                i for i in candidates
                if self._meta[i].get("type") == type_filter
            ]
        if source_filter and source_filter != "all":
            candidates = [
                i for i in candidates
                if self._meta[i].get("source_dir") == source_filter
                or str(self._meta[i].get("canonical_key", "")).startswith(f"{source_filter}/")
            ]

        candidates.sort(key=lambda i: scores[i], reverse=True)
        top = candidates[:top_k]

        results = []
        for idx in top:
            s = float(scores[idx])
            if s < min_score:
                break
            meta = self._meta[idx]
            canonical_key = meta.get("canonical_key", meta.get("file_name", meta.get("id", "")))
            full_text = _load_full_text(
                meta.get("file_name", meta.get("id", "")), _entry_source_dir(meta)
            )
            results.append({
                "score": round(s, 4),
                "text": full_text,
                "canonical_key": canonical_key,
                "metadata": meta,
            })
        return results

    # ── 单条 upsert ─────────────────────────────────────────

    def upsert(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        """插入或更新单条经验。保存到磁盘。"""
        vec = encode_safe(text)
        if vec is None:
            return

        vec = vec.astype(np.float32).reshape(1, -1)
        metadata["text"] = text
        metadata.setdefault("source_dir", "experiences")
        metadata.setdefault("canonical_key", f"{metadata['source_dir']}/{doc_id}")

        if (self._embs is None or len(self._meta) == 0) and EMB_PATH.exists() and META_PATH.exists():
            self.load()

        if self._embs is None or len(self._meta) == 0:
            self._embs = vec
            self._meta = [metadata]
        else:
            existing = next(
                (i for i, m in enumerate(self._meta)
                 if m.get("canonical_key") == metadata.get("canonical_key")
                 or m.get("id") == doc_id
                 or m.get("file_name") == doc_id),
                None,
            )
            if existing is not None:
                self._embs[existing] = vec[0]
                self._meta[existing] = metadata
            else:
                self._embs = np.vstack([self._embs, vec])  # type: ignore[arg-type]
                self._meta.append(metadata)

        self.save()

    @property
    def count(self) -> int:
        return len(self._meta)

    @property
    def is_available(self) -> bool:
        return self._embs is not None and len(self._meta) > 0
