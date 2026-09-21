import json
import shutil
import tempfile
import unittest
from pathlib import Path

from toolkit.core.control_codes import extract_control_codes, repair_control_codes
from toolkit.models import ProjectInfo, TranslationEntry
from toolkit.rpgmaker import RPGMakerService
from toolkit.unknown_game import (
    detect_mtool_installation,
    generate_mtool_patch_bundle,
    UnknownGameService,
)


class TestMToolFeatures(unittest.TestCase):
    def test_control_codes_extraction_and_repair(self):
        source = r"你好，\N[1]！你的等级是 \V[2]，拥有 $1 金币和 [item_name]。状态：%s，颜色 \C[4] 提示！"
        codes = extract_control_codes(source)
        self.assertIn(r"\N[1]", codes)
        self.assertIn(r"\V[2]", codes)
        self.assertIn("$1", codes)
        self.assertIn("[item_name]", codes)
        self.assertIn("%s", codes)
        self.assertIn(r"\C[4]", codes)

        # AI hallucinated corrupted translation: \n[1] instead of \N[1], /V[2] instead of \V[2], lost $1, ％s instead of %s
        corrupted_target = "你好，\\n[1]！你的等级是 /V[2]，拥有  金币和 【item_name】。状态：％s，颜色 \\c[4] 提示！"
        repaired = repair_control_codes(source, corrupted_target)
        self.assertIn(r"\N[1]", repaired)
        self.assertIn(r"\V[2]", repaired)
        self.assertIn("$1", repaired)
        self.assertIn("[item_name]", repaired)
        self.assertIn("%s", repaired)
        self.assertIn(r"\C[4]", repaired)

    def test_save_snapshots_and_rollback(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="rpgrtl_test_saves_"))
        try:
            (tmp_dir / "data").mkdir(parents=True)
            save_dir = tmp_dir / "save"
            save_dir.mkdir(parents=True)
            save_file = save_dir / "file1.rpgsave"
            save_file.write_bytes(b"initial_save_content_1")

            project = ProjectInfo(
                engine="RPG Maker MV/MZ",
                root=tmp_dir,
                game_dir=tmp_dir,
                launcher_path=None,
                data_dir=tmp_dir / "data",
            )
            service = RPGMakerService(project)

            # 1. Create snapshot
            res = service.create_save_snapshot("测试快照A")
            self.assertTrue(res["ok"])
            snapshot_id = res["snapshot"]["id"]

            # 2. List snapshots
            snapshots = service.list_save_snapshots()
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0]["id"], snapshot_id)

            # 3. Simulate corrupting or modifying save
            save_file.write_bytes(b"modified_or_corrupted_data")
            self.assertEqual(save_file.read_bytes(), b"modified_or_corrupted_data")

            # 4. Restore snapshot
            rest_res = service.restore_save_snapshot(snapshot_id)
            self.assertTrue(rest_res["ok"])
            self.assertEqual(save_file.read_bytes(), b"initial_save_content_1")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_mtool_patch_bundle_bakin(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="rpgrtl_test_bakin_"))
        try:
            (tmp_dir / "data").mkdir(parents=True)
            (tmp_dir / "data" / "bakinplayer.exe").write_bytes(b"MZ")

            project = ProjectInfo(
                engine="RPG Developer Bakin",
                root=tmp_dir,
                game_dir=tmp_dir,
                launcher_path=tmp_dir / "data" / "bakinplayer.exe",
            )
            entries = [
                TranslationEntry("bakin_1", "Start Game", "开始游戏"),
                TranslationEntry("bakin_2", "Options", "设置"),
            ]

            bundle_res = generate_mtool_patch_bundle(
                project=project,
                entries=entries,
                font_name="SimHei",
                font_size_offset=-2,
                target_dir=tmp_dir,
            )
            self.assertTrue(bundle_res["ok"])
            self.assertTrue((tmp_dir / "翻译文件.json").is_file())
            self.assertTrue((tmp_dir / "与工具一同启动.bat").is_file())
            self.assertTrue((tmp_dir / "从游戏中移除工具文件.bat").is_file())
            self.assertTrue((tmp_dir / "data" / "lastLoadedTrsFile").is_file())
            self.assertTrue((tmp_dir / "data" / "fixFontName").is_file())
            self.assertTrue((tmp_dir / "data" / "fixFontSizeOffBakin").is_file())

            # Verify contents
            trs_content = json.loads((tmp_dir / "翻译文件.json").read_text(encoding="utf-8"))
            self.assertEqual(trs_content["Start Game"], "开始游戏")
            self.assertEqual((tmp_dir / "data" / "fixFontName").read_text(encoding="utf-8").strip(), "SimHei")
            self.assertEqual((tmp_dir / "data" / "fixFontSizeOffBakin").read_text(encoding="utf-8").strip(), "-2")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_mtool_patch_bundle_wolf(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="rpgrtl_test_wolf_"))
        try:
            (tmp_dir / "Game.exe").write_bytes(b"MZ")
            (tmp_dir / "Data").mkdir(parents=True)
            (tmp_dir / "Data" / "BasicData").mkdir(parents=True)

            project = ProjectInfo(
                engine="Wolf RPG Editor",
                root=tmp_dir,
                game_dir=tmp_dir,
                launcher_path=tmp_dir / "Game.exe",
            )
            entries = {"Attack": "攻击", "Defend": "防御"}

            bundle_res = generate_mtool_patch_bundle(
                project=project,
                entries=entries,
                font_size_offset=-1,
                target_dir=tmp_dir,
            )
            self.assertTrue(bundle_res["ok"])
            self.assertTrue((tmp_dir / "翻译文件.json").is_file())
            self.assertTrue((tmp_dir / "与工具一同启动.bat").is_file())
            self.assertTrue((tmp_dir / "从游戏中移除工具文件.bat").is_file())

            trs_content = json.loads((tmp_dir / "翻译文件.json").read_text(encoding="utf-8"))
            self.assertEqual(trs_content["Attack"], "攻击")
            self.assertEqual(trs_content["Defend"], "防御")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_mtool_detection(self):
        res = detect_mtool_installation()
        self.assertIsInstance(res, dict)
        self.assertIn("installed", res)
        self.assertIn("loaders_dir", res)


if __name__ == "__main__":
    unittest.main()
