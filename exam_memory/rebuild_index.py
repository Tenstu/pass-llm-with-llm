"""rebuild_index.py — CLI 全量重建向量索引。

用法:
    python -m exam_memory.rebuild_index                # 全量重建
    python -m exam_memory.rebuild_index --type 算法    # 只重建算法类
    python -m exam_memory.rebuild_index --force        # 强制覆盖已有索引
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(
        description="exam-memory 向量索引全量重建"
    )
    ap.add_argument("--type", choices=["单选题", "多选题", "算法"],
                    help="仅重建指定类型的经验")
    ap.add_argument("--force", action="store_true",
                    help="强制覆盖已有索引")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    from exam_memory.vector_store import NumpyVectorStore
    from exam_memory.embedding import is_available, EmbeddingError

    if not is_available():
        print("[rebuild] embedding 不可用，请先安装: pip install '.[embed]'",
              file=sys.stderr)
        return 1

    store = NumpyVectorStore()
    if not args.force and store.is_available:
        n = store.count
        print(f"[rebuild] 索引已存在（{n} 条），加 --force 强制覆盖")
        return 0

    n = store.rebuild(verbose=args.verbose)
    if n == 0:
        print("[rebuild] 未索引任何经验（experiences/ 目录可能为空）")
        return 1

    print(f"[rebuild] 完成: {n} 条经验已向量化")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
