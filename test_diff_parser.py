import unittest
from backend.github_handler import GitHubHandler

class TestDiffParser(unittest.TestCase):
    def setUp(self):
        self.handler = GitHubHandler()

    def test_single_file_single_hunk(self):
        diff = """diff --git a/backend/main.py b/backend/main.py
index 1234567..abcdefg 100644
--- a/backend/main.py
+++ b/backend/main.py
@@ -1,5 +1,6 @@
 import os
+import sys
 from fastapi import FastAPI
 
 def main():
-    pass
+    print("hello")
"""
        result = self.handler.parse_diff(diff)
        self.assertIn("backend/main.py", result)
        # line numbers in new file:
        # line 1: import os (unchanged)
        # line 2: +import sys (added) -> valid!
        # line 3: from fastapi import FastAPI (unchanged)
        # line 4: (empty line) (unchanged)
        # line 5: def main(): (unchanged)
        # line 6: +    print("hello") (added) -> valid!
        self.assertEqual(result["backend/main.py"], {2, 6})

    def test_multiple_files(self):
        diff = """diff --git a/file1.py b/file1.py
index 123..456 100644
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,3 @@
 line1
+line2
 line3
diff --git a/file2.py b/file2.py
index 789..012 100644
--- a/file2.py
+++ b/file2.py
@@ -10,3 +10,5 @@
 old_line
+new_line_1
+new_line_2
 context_line
"""
        result = self.handler.parse_diff(diff)
        self.assertEqual(result["file1.py"], {2})
        self.assertEqual(result["file2.py"], {11, 12})

    def test_no_changes(self):
        diff = """diff --git a/file.py b/file.py
index 123..456 100644
--- a/file.py
+++ b/file.py
"""
        result = self.handler.parse_diff(diff)
        self.assertEqual(result, {})

    def test_deleted_file(self):
        diff = """diff --git a/deleted.py b/deleted.py
deleted file mode 100644
index 123..0000000
--- a/deleted.py
+++ /dev/null
@@ -1,2 +0,0 @@
-line1
-line2
"""
        result = self.handler.parse_diff(diff)
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main()
