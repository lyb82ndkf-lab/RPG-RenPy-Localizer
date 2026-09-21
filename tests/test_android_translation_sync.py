import json
import re
import unittest
from pathlib import Path

class TestAndroidTranslationSync(unittest.TestCase):
    def setUp(self):
        # Android 端 TranslationManager 中的控制代码正则
        self.control_regex = re.compile(
            r"\\[A-Za-z]+(?:\[[^\]\r\n]{0,128}\])?"
            r"|\$\{[^}\r\n]{1,160}\}"
            r"|\{(?:\d+|[A-Za-z_][A-Za-z0-9_.-]{0,80})\}"
            r"|%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[diuoxXfFeEgGcs]"
            r"|<[/!]?[A-Za-z][^>\r\n]{0,160}>"
            r"|\[\[VAR_[^\]]+\]\]"
        )

    def extract_tokens(self, text: str) -> list[str]:
        return [match.group(0) for match in self.control_regex.finditer(text or "")]

    def check_loss(self, source: str, target: str) -> bool:
        if not target.strip():
            return False
        tokens = self.extract_tokens(source)
        for token in tokens:
            if token not in target:
                return True
        return False

    def test_control_codes_parity(self):
        # RPG Maker 控制符
        src = "获得了 \\V[10] 个 \\C[2]金币\\C[0]！"
        tgt_good = "Received \\V[10] \\C[2]Gold Coins\\C[0]!"
        tgt_bad = "Received 10 Gold Coins!"

        self.assertFalse(self.check_loss(src, tgt_good))
        self.assertTrue(self.check_loss(src, tgt_bad))

        # MTool 变量
        src_mtool = "你好，[[VAR_0]]，欢迎来到村庄。"
        tgt_mtool_good = "Hello, [[VAR_0]], welcome to town."
        tgt_mtool_bad = "Hello, adventurer, welcome to town."

        self.assertFalse(self.check_loss(src_mtool, tgt_mtool_good))
        self.assertTrue(self.check_loss(src_mtool, tgt_mtool_bad))

        # Ren'Py / Python 格式化
        src_renpy = "Level {0} - Score %d"
        tgt_renpy_good = "等级 {0} - 分数 %d"
        tgt_renpy_bad = "等级 - 分数"

        self.assertFalse(self.check_loss(src_renpy, tgt_renpy_good))
        self.assertTrue(self.check_loss(src_renpy, tgt_renpy_bad))

    def test_json_dictionary_format(self):
        # 验证导出的 翻译文件.json 为 UTF-8 标准字典
        sample = {
            "勇者よ、目覚めなさい。": "勇者啊，醒来吧。",
            "所持金: \\V[1] G": "持金: \\V[1] G"
        }
        encoded = json.dumps(sample, ensure_ascii=False, indent=2)
        decoded = json.loads(encoded)
        self.assertEqual(sample, decoded)
        self.assertEqual(decoded["所持金: \\V[1] G"], "持金: \\V[1] G")

if __name__ == "__main__":
    unittest.main()
