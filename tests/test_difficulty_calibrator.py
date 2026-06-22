"""tests/test_difficulty_calibrator.py — DifficultyCalibrator 单元测试。

覆盖: 无历史返回建议值 / 历史记录后自动升级降级 / JSON 持久化 /
     边界正确率恰好 0.5 的处理 / QuestionBank 集成
运行: pytest tests/test_difficulty_calibrator.py -v
"""
from __future__ import annotations

import json

import pytest

from exam_memory.difficulty_calibrator import DifficultyCalibrator


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def calibrator(tmp_path):
    """使用临时目录的 DifficultyCalibrator（自动持久化到 tmp_path）。"""
    stats_file = tmp_path / "stats.json"
    c = DifficultyCalibrator(stats_path=str(stats_file))
    c.clear()
    return c


# ── 无历史数据 → 返回建议值 ────────────────────────────────────

class TestNoHistoryReturnsSuggested:
    def test_returns_suggested_when_no_data(self, calibrator):
        assert calibrator.calibrate("任意知识点", "简单") == "简单"
        assert calibrator.calibrate("任意知识点", "中等") == "中等"
        assert calibrator.calibrate("任意知识点", "困难") == "困难"

    def test_returns_suggested_for_new_knowledge(self, calibrator):
        """已有其他知识点的数据，新知识点仍返回建议值。"""
        calibrator.record_result("已知知识点", "简单", correct=True)
        assert calibrator.calibrate("全新知识点", "困难") == "困难"


# ── 历史记录后自动升级/降级 ────────────────────────────────────

class TestCalibrationWithHistory:
    def test_high_correct_rate_downgrades_to_easy(self, calibrator):
        """正确率 >= 80% 时校准为"简单"。"""
        for _ in range(10):
            calibrator.record_result("DP", "困难", correct=True)
        result = calibrator.calibrate("DP", "困难")
        assert result == "简单"

    def test_medium_correct_rate_stays_middle(self, calibrator):
        """正确率 50%-80% 时校准为"中等"。"""
        # 10 题答对 6 题 → 60% → 中等
        for i in range(10):
            calibrator.record_result("排序", "中等", correct=(i < 6))
        result = calibrator.calibrate("排序", "中等")
        assert result == "中等"

    def test_low_correct_rate_upgrades_to_hard(self, calibrator):
        """正确率 < 50% 时校准为"困难"。"""
        # 10 题答对 3 题 → 30% → 困难
        for i in range(10):
            calibrator.record_result("图论", "中等", correct=(i < 3))
        result = calibrator.calibrate("图论", "中等")
        assert result == "困难"

    def test_mixed_difficulties_aggregated(self, calibrator):
        """同一知识点下不同难度的记录按总正确率聚合。"""
        calibrator.record_result("树", "简单", correct=True)
        calibrator.record_result("树", "简单", correct=True)
        calibrator.record_result("树", "困难", correct=False)
        calibrator.record_result("树", "困难", correct=False)
        # total=4, correct=2 → 50% → 中等
        result = calibrator.calibrate("树", "困难")
        assert result == "中等"

    def test_all_correct_rate_downgrades(self, calibrator):
        """全对时即使建议"困难"也降级为"简单"。"""
        for _ in range(5):
            calibrator.record_result("字符串", "困难", correct=True)
        assert calibrator.calibrate("字符串", "困难") == "简单"

    def test_none_correct_remains_hard(self, calibrator):
        """全错时即使建议"简单"也升级为"困难"。"""
        for _ in range(5):
            calibrator.record_result("数学", "简单", correct=False)
        assert calibrator.calibrate("数学", "简单") == "困难"


# ── 边界：正确率恰好 0.5 → "中等" ──────────────────────────────

class TestBoundaryRate050:
    def test_exactly_half_correct_is_middle(self, calibrator):
        """正确率恰好 50% 应判定为"中等"（>= 0.5 匹配中等）。"""
        for i in range(10):
            calibrator.record_result("网络", "中等", correct=(i < 5))
        result = calibrator.calibrate("网络", "中等")
        assert result == "中等"

    def test_just_above_half_is_middle(self, calibrator):
        """正确率 51% 应判定为"中等"。"""
        results = [True] * 51 + [False] * 49
        for correct in results:
            calibrator.record_result("OS", "中等", correct=correct)
        assert calibrator.calibrate("OS", "中等") == "中等"

    def test_just_below_half_is_hard(self, calibrator):
        """正确率 49% 应判定为"困难"。"""
        results = [True] * 49 + [False] * 51
        for correct in results:
            calibrator.record_result("DB", "中等", correct=correct)
        assert calibrator.calibrate("DB", "中等") == "困难"


# ── JSON 持久化 ─────────────────────────────────────────────────

class TestJsonPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        stats_file = tmp_path / "stats.json"
        c1 = DifficultyCalibrator(stats_path=str(stats_file))
        c1.record_result("DP", "困难", correct=True)
        c1.record_result("DP", "困难", correct=False)
        c1.record_result("图", "简单", correct=True)
        c1.save()

        # 新建实例加载
        c2 = DifficultyCalibrator(stats_path=str(stats_file))
        assert c2.calibrate("DP", "困难") == "中等"   # 50% → 中等
        assert c2.calibrate("图", "简单") == "简单"    # 100% → 简单（但无历史时返回建议...）
        assert c2.calibrate("图", "简单") == "简单"    # 100% → 简单
        assert c2.calibrate("新知识", "困难") == "困难"  # 无历史时返回建议

    def test_missing_file_initializes_empty(self, tmp_path):
        stats_file = tmp_path / "nonexistent" / "stats.json"
        c = DifficultyCalibrator(stats_path=str(stats_file))
        assert c.calibrate("x", "简单") == "简单"

    def test_corrupted_file_graceful_fallback(self, tmp_path):
        stats_file = tmp_path / "stats.json"
        stats_file.write_text("not valid json{{{", encoding="utf-8")
        c = DifficultyCalibrator(stats_path=str(stats_file))
        # 不应抛异常，降级为空状态
        assert c.calibrate("x", "中等") == "中等"

    def test_clear_resets_data(self, calibrator):
        calibrator.record_result("K", "简单", correct=True)
        calibrator.clear()
        assert calibrator.calibrate("K", "困难") == "困难"


# ── get_stats / DIFFICULTY_OPTIONS ──────────────────────────────

class TestUtilityMethods:
    def test_get_stats_specific_knowledge(self, calibrator):
        calibrator.record_result("DP", "简单", correct=True)
        calibrator.record_result("DP", "困难", correct=False)
        stats = calibrator.get_stats("DP")
        assert "简单" in stats
        assert "困难" in stats
        assert stats["简单"]["total"] == 1
        assert stats["简单"]["correct"] == 1

    def test_get_stats_all(self, calibrator):
        calibrator.record_result("A", "简单", correct=True)
        calibrator.record_result("B", "困难", correct=False)
        all_stats = calibrator.get_stats()
        assert "A" in all_stats
        assert "B" in all_stats

    def test_difficulty_options_constant(self):
        assert DifficultyCalibrator.DIFFICULTY_OPTIONS == ("简单", "中等", "困难")

    def test_thresholds_constant(self):
        assert DifficultyCalibrator.THRESHOLDS == {
            "简单": 0.8,
            "中等": 0.5,
            "困难": 0.0,
        }


# ── QuestionBank 集成 ───────────────────────────────────────────

class TestQuestionBankIntegration:
    def test_custom_bank_dir_keeps_difficulty_stats_local(self, tmp_path, monkeypatch):
        """QuestionBank(bank_dir=...) 不应写入默认运行态 stats 文件。"""
        import exam_memory.question_bank as qb

        default_dir = tmp_path / "default_bank"
        custom_dir = tmp_path / "custom_bank"
        monkeypatch.setattr(qb, "BANK_DIR", default_dir)

        bank = qb.QuestionBank(bank_dir=custom_dir)
        bank._calibrator.record_result("双指针", "困难", correct=True)

        assert (custom_dir / "difficulty_stats.json").exists()
        assert not (default_dir / "difficulty_stats.json").exists()

    def test_calibrate_difficulty_adjusts_frontmatter(self, tmp_path):
        """calibrate_difficulty=True 时 frontmatter 中的 difficulty 被校准。"""
        from exam_memory.question_bank import QuestionBank
        bank = QuestionBank(bank_dir=tmp_path)
        # 先记录一些答题历史，使"双指针"的正确率 >= 80%
        for _ in range(10):
            bank._calibrator.record_result("双指针", "困难", correct=True)

        fn = bank.add_manual(
            title="两数之和",
            content="给定数组和目标值，找两数之和。",
            q_type="算法",
            knowledge="双指针",
            answer="C",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            difficulty="困难",
            calibrate_difficulty=True,
        )
        text = (tmp_path / fn).read_text(encoding="utf-8")
        assert "difficulty: 简单" in text  # 被校准为简单
        assert "difficulty_suggested: 困难" in text  # 原始建议保留

    def test_calibrate_difficulty_false_no_change(self, tmp_path):
        """calibrate_difficulty=False（默认）时不做校准。"""
        from exam_memory.question_bank import QuestionBank
        bank = QuestionBank(bank_dir=tmp_path)
        # 即使有历史数据，calibrate_difficulty=False 也不校准
        for _ in range(10):
            bank._calibrator.record_result("哈希表", "困难", correct=True)

        fn = bank.add_manual(
            title="哈希查找",
            content="用哈希表查找。",
            q_type="算法",
            knowledge="哈希表",
            answer="A",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            difficulty="困难",
            calibrate_difficulty=False,
        )
        text = (tmp_path / fn).read_text(encoding="utf-8")
        assert "difficulty: 困难" in text
        assert "difficulty_suggested" not in text

    def test_add_dict_passes_calibrate(self, tmp_path):
        """add() 的 calibrate_difficulty 参数透传到 add_manual。"""
        from exam_memory.question_bank import QuestionBank
        bank = QuestionBank(bank_dir=tmp_path)
        # 让"DP"的正确率达到中等水平
        for i in range(10):
            bank._calibrator.record_result("动态规划", "困难", correct=(i < 5))

        fn = bank.add(
            {
                "title": "DP 基础",
                "content": "动态规划描述",
                "type": "算法",
                "knowledge": "动态规划",
                "answer": "A",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                "difficulty": "困难",
            },
            calibrate_difficulty=True,
        )
        text = (tmp_path / fn).read_text(encoding="utf-8")
        assert "difficulty: 中等" in text

    def test_no_history_keeps_original_difficulty(self, tmp_path):
        """无历史时即使 calibrate_difficulty=True 也不改变难度。"""
        from exam_memory.question_bank import QuestionBank
        bank = QuestionBank(bank_dir=tmp_path)

        fn = bank.add_manual(
            title="冷门题",
            content="非常冷门的内容。",
            q_type="算法",
            knowledge="生僻知识点",
            answer="B",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            difficulty="中等",
            calibrate_difficulty=True,
        )
        text = (tmp_path / fn).read_text(encoding="utf-8")
        assert "difficulty: 中等" in text
        assert "difficulty_suggested" not in text
