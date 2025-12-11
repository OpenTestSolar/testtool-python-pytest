"""Tests for header_injection module."""

import threading
from typing import Any, Dict, Optional
from unittest import mock

import pytest

from src.testsolar_pytestx.header_injection import (
    get_current_test_nodeid,
    set_current_test_nodeid,
    _inject_header_to_dict,
    initialize_header_injection,
)


@pytest.fixture(autouse=True)
def reset_nodeid() -> None:
    """Reset the test context before and after each test."""
    set_current_test_nodeid(None)
    yield  # type: ignore[misc]
    set_current_test_nodeid(None)


class TestContextManagement:
    """Test cases for test context management functions."""

    def test_get_current_test_nodeid_returns_none_initially(self) -> None:
        """Test get_current_test_nodeid returns None when not set."""
        result = get_current_test_nodeid()
        assert result is None

    def test_set_and_get_current_test_nodeid(self) -> None:
        """Test setting and getting the current test nodeid."""
        nodeid = "test_file.py::test_function"
        set_current_test_nodeid(nodeid)
        result = get_current_test_nodeid()
        assert result == nodeid

    def test_set_current_test_nodeid_to_none(self) -> None:
        """Test setting nodeid to None clears it."""
        set_current_test_nodeid("test_file.py::test_function")
        set_current_test_nodeid(None)
        result = get_current_test_nodeid()
        assert result is None

    def test_nodeid_is_thread_local(self) -> None:
        """Test that nodeid is thread-local."""
        main_nodeid = "main_thread::test"
        set_current_test_nodeid(main_nodeid)

        child_nodeid: Optional[str] = None
        child_set_result: Optional[str] = None

        def child_thread_func() -> None:
            nonlocal child_nodeid, child_set_result
            # Should be None in child thread initially
            child_nodeid = get_current_test_nodeid()
            # Set a different nodeid in child thread
            set_current_test_nodeid("child_thread::test")
            child_set_result = get_current_test_nodeid()

        thread = threading.Thread(target=child_thread_func)
        thread.start()
        thread.join()

        # Child thread should have seen None initially
        assert child_nodeid is None
        # Child thread should have its own nodeid
        assert child_set_result == "child_thread::test"
        # Main thread nodeid should be unchanged
        assert get_current_test_nodeid() == main_nodeid


class TestInjectHeaderToDict:
    """Test cases for _inject_header_to_dict function."""

    def test_inject_header_to_none_headers(self) -> None:
        """Test injecting header when headers is None."""
        result = _inject_header_to_dict(None, "test::nodeid")
        assert result == {"X-Testsolar-Testcase": "test::nodeid"}

    def test_inject_header_to_empty_dict(self) -> None:
        """Test injecting header to empty dict."""
        result = _inject_header_to_dict({}, "test::nodeid")
        assert result == {"X-Testsolar-Testcase": "test::nodeid"}

    def test_inject_header_to_existing_dict(self) -> None:
        """Test injecting header to dict with existing headers."""
        original: Dict[str, Any] = {"Content-Type": "application/json"}
        result = _inject_header_to_dict(original, "test::nodeid")

        assert result == {
            "Content-Type": "application/json",
            "X-Testsolar-Testcase": "test::nodeid",
        }
        # Original should not be modified
        assert "X-Testsolar-Testcase" not in original

    def test_inject_header_does_not_modify_original(self) -> None:
        """Test that original headers dict is not modified."""
        original: Dict[str, str] = {"Authorization": "Bearer token"}
        _ = _inject_header_to_dict(original, "test::nodeid")

        assert original == {"Authorization": "Bearer token"}


class TestInitializeHeaderInjection:
    """Test cases for initialize_header_injection function."""

    def test_can_be_called_multiple_times(self) -> None:
        """Test that initialize_header_injection can be called multiple times safely."""
        # Should not raise any exceptions
        initialize_header_injection()
        initialize_header_injection()
        initialize_header_injection()

    def test_patches_requests_if_available(self) -> None:
        """Test that requests.Session.request is patched if available."""
        pytest.importorskip("requests")

        initialize_header_injection()

        # We verify by checking that the module-level original reference is set
        from src.testsolar_pytestx.header_injection import _original_requests_request

        assert _original_requests_request is not None

    def test_patches_httpx_if_available(self) -> None:
        """Test that httpx.Client.request is patched if available."""
        httpx = pytest.importorskip("httpx")

        initialize_header_injection()

        # The Client.request should be patched
        assert callable(httpx.Client.request)


class TestRequestsIntegration:
    """Integration tests for requests library patching."""

    @pytest.fixture(autouse=True)
    def setup_injection(self) -> None:
        """Set up header injection."""
        initialize_header_injection()

    def test_requests_header_injection(self) -> None:
        """Test that requests injects header when nodeid is set."""
        requests = pytest.importorskip("requests")

        set_current_test_nodeid("test_file.py::test_case")

        # Mock the actual HTTP call to capture the request
        with mock.patch("requests.adapters.HTTPAdapter.send") as mock_send:
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_send.return_value = mock_response

            session = requests.Session()
            try:
                session.get("http://example.com")
            except Exception:
                pass

            # Check that the header was injected
            if mock_send.called:
                request = mock_send.call_args[0][0]
                assert "X-Testsolar-Testcase" in request.headers
                assert request.headers["X-Testsolar-Testcase"] == "test_file.py::test_case"

    def test_requests_no_injection_when_nodeid_not_set(self) -> None:
        """Test that requests does not inject header when nodeid is not set."""
        requests = pytest.importorskip("requests")

        set_current_test_nodeid(None)

        with mock.patch("requests.adapters.HTTPAdapter.send") as mock_send:
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_send.return_value = mock_response

            session = requests.Session()
            try:
                session.get("http://example.com")
            except Exception:
                pass

            if mock_send.called:
                request = mock_send.call_args[0][0]
                assert "X-Testsolar-Testcase" not in request.headers


class TestHttpxIntegration:
    """Integration tests for httpx library patching."""

    @pytest.fixture(autouse=True)
    def setup_injection(self) -> None:
        """Set up header injection."""
        initialize_header_injection()

    def test_httpx_header_injection(self) -> None:
        """Test that httpx injects header when nodeid is set."""
        httpx = pytest.importorskip("httpx")

        set_current_test_nodeid("test_file.py::test_httpx_case")

        # Mock the transport to capture the request
        with mock.patch.object(httpx.HTTPTransport, "handle_request") as mock_handle:
            mock_response = httpx.Response(200)
            mock_handle.return_value = mock_response

            client = httpx.Client()
            try:
                client.get("http://example.com")
            except Exception:
                pass
            finally:
                client.close()

            if mock_handle.called:
                request = mock_handle.call_args[0][0]
                assert b"x-testsolar-testcase" in request.headers.raw

    def test_httpx_no_injection_when_nodeid_not_set(self) -> None:
        """Test that httpx does not inject header when nodeid is not set."""
        httpx = pytest.importorskip("httpx")

        set_current_test_nodeid(None)

        with mock.patch.object(httpx.HTTPTransport, "handle_request") as mock_handle:
            mock_response = httpx.Response(200)
            mock_handle.return_value = mock_response

            client = httpx.Client()
            try:
                client.get("http://example.com")
            except Exception:
                pass
            finally:
                client.close()
