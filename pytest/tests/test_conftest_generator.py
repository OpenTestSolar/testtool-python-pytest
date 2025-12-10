"""Tests for conftest_generator module."""

import tempfile
from pathlib import Path

from src.testsolar_pytestx.conftest_generator import (
    CONFTEST_MARKER,
    CONFTEST_TEMPLATE,
    _is_testsolar_conftest,
    _backup_existing_conftest,
    _merge_conftest_content,
    generate_conftest_for_header_injection,
    cleanup_generated_conftest,
)


class TestIsTestsolarConftest:
    """Test cases for _is_testsolar_conftest function."""

    def test_returns_false_for_nonexistent_file(self) -> None:
        """Test _is_testsolar_conftest returns False for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            assert _is_testsolar_conftest(conftest_path) is False

    def test_returns_true_for_testsolar_generated(self) -> None:
        """Test _is_testsolar_conftest returns True for testsolar-generated file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            conftest_path.write_text(CONFTEST_TEMPLATE, encoding="utf-8")
            assert _is_testsolar_conftest(conftest_path) is True

    def test_returns_false_for_user_conftest(self) -> None:
        """Test _is_testsolar_conftest returns False for user-created conftest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            conftest_path.write_text("# user conftest\nimport pytest\n", encoding="utf-8")
            assert _is_testsolar_conftest(conftest_path) is False


class TestBackupExistingConftest:
    """Test cases for _backup_existing_conftest function."""

    def test_returns_none_for_nonexistent(self) -> None:
        """Test _backup_existing_conftest returns None for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            result = _backup_existing_conftest(conftest_path)
            assert result is None

    def test_returns_none_for_testsolar_generated(self) -> None:
        """Test _backup_existing_conftest returns None for testsolar-generated file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            conftest_path.write_text(CONFTEST_TEMPLATE, encoding="utf-8")
            result = _backup_existing_conftest(conftest_path)
            assert result is None

    def test_creates_backup_for_user_conftest(self) -> None:
        """Test _backup_existing_conftest creates backup for user conftest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            user_content = "# user conftest\nimport pytest\n"
            conftest_path.write_text(user_content, encoding="utf-8")

            result = _backup_existing_conftest(conftest_path)

            assert result is not None
            backup_path = Path(result)
            assert backup_path.exists()
            assert backup_path.read_text(encoding="utf-8") == user_content


class TestMergeConftestContent:
    """Test cases for _merge_conftest_content function."""

    def test_adds_template_to_existing(self) -> None:
        """Test _merge_conftest_content adds template to existing content."""
        existing_content = "# user conftest\nimport pytest\n"
        merged = _merge_conftest_content(existing_content, CONFTEST_TEMPLATE)

        assert CONFTEST_MARKER in merged
        assert "# user conftest" in merged
        assert "Original conftest.py content below" in merged

    def test_does_not_duplicate(self) -> None:
        """Test _merge_conftest_content does not duplicate if already merged."""
        existing_content = CONFTEST_TEMPLATE + "\n# user code"
        merged = _merge_conftest_content(existing_content, CONFTEST_TEMPLATE)

        # Should return the existing content unchanged
        assert merged == existing_content


class TestGenerateConftestForHeaderInjection:
    """Test cases for generate_conftest_for_header_injection function."""

    def test_creates_new_file(self) -> None:
        """Test generate_conftest_for_header_injection creates new conftest.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_conftest_for_header_injection(tmpdir)

            assert result is not None
            conftest_path = Path(tmpdir) / "conftest.py"
            assert conftest_path.exists()
            content = conftest_path.read_text(encoding="utf-8")
            assert CONFTEST_MARKER in content

    def test_updates_existing_testsolar_conftest(self) -> None:
        """Test generate_conftest_for_header_injection updates existing testsolar conftest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            # Write an old version of testsolar conftest
            old_content = f'"""\n{CONFTEST_MARKER}\nOLD VERSION\n"""\n'
            conftest_path.write_text(old_content, encoding="utf-8")

            result = generate_conftest_for_header_injection(tmpdir)

            assert result is not None
            content = conftest_path.read_text(encoding="utf-8")
            # Should be updated to new template
            assert content == CONFTEST_TEMPLATE

    def test_merges_with_user_conftest(self) -> None:
        """Test generate_conftest_for_header_injection merges with user conftest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            user_content = "# user conftest\nimport pytest\n\ndef my_fixture():\n    pass\n"
            conftest_path.write_text(user_content, encoding="utf-8")

            result = generate_conftest_for_header_injection(tmpdir)

            assert result is not None
            content = conftest_path.read_text(encoding="utf-8")
            # Should contain both marker and user content
            assert CONFTEST_MARKER in content
            assert "# user conftest" in content
            assert "my_fixture" in content

            # Backup should exist
            backup_path = conftest_path.with_suffix(".py.testsolar_backup")
            assert backup_path.exists()


class TestCleanupGeneratedConftest:
    """Test cases for cleanup_generated_conftest function."""

    def test_removes_pure_testsolar_conftest(self) -> None:
        """Test cleanup_generated_conftest removes pure testsolar conftest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            conftest_path.write_text(CONFTEST_TEMPLATE, encoding="utf-8")

            cleanup_generated_conftest(tmpdir)

            assert not conftest_path.exists()

    def test_restores_from_backup(self) -> None:
        """Test cleanup_generated_conftest restores from backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            backup_path = conftest_path.with_suffix(".py.testsolar_backup")

            user_content = "# user conftest\nimport pytest\n"
            backup_path.write_text(user_content, encoding="utf-8")
            conftest_path.write_text(CONFTEST_TEMPLATE + user_content, encoding="utf-8")

            cleanup_generated_conftest(tmpdir)

            assert conftest_path.exists()
            assert not backup_path.exists()
            assert conftest_path.read_text(encoding="utf-8") == user_content

    def test_does_not_remove_merged_conftest(self) -> None:
        """Test cleanup_generated_conftest does not remove merged conftest without backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            conftest_path = Path(tmpdir) / "conftest.py"
            merged_content = (
                CONFTEST_TEMPLATE
                + "\n\n# === Original conftest.py content below ===\n\n# user code"
            )
            conftest_path.write_text(merged_content, encoding="utf-8")

            cleanup_generated_conftest(tmpdir)

            # Should still exist because it contains merged content
            assert conftest_path.exists()
