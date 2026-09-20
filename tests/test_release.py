"""Package integrity checks: importable Python, JSON, references and no local-user paths."""
import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_python_and_json_parse(self):
        for path in ROOT.rglob('*'):
            if path.suffix == '.py':
                ast.parse(path.read_text(encoding='utf-8'))
            if path.suffix == '.json':
                json.loads(path.read_text(encoding='utf-8'))

    def test_markdown_file_links_resolve(self):
        for path in ROOT.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in link or link.startswith('#'):
                    continue
                target = (path.parent / link.split('#')[0]).resolve()
                self.assertTrue(target.is_file(), f'{path.name}: missing {link}')

    def test_no_machine_home_paths_or_private_key_material(self):
        for path in ROOT.rglob('*'):
            if not path.is_file() or path.suffix not in ('.md', '.json', '.yaml', '.yml', '.py'):
                continue
            text = path.read_text(encoding='utf-8')
            self.assertFalse(re.search(r'/home/[A-Za-z0-9_-]+/', text), path.name)
            self.assertFalse(re.search(r'BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY', text), path.name)


if __name__ == '__main__':
    unittest.main()
