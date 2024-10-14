import io
import sys
import pytest
import contextlib
from typing import List, Tuple, TextIO, TypeVar

T = TypeVar("T")

MAX_CHAR_SIZE = int(100 * 1024 * 1024 / 8 / 4)  # 100MB 对应的UTF-8编码字符数


def exceeds_max_size(stream: TextIO) -> bool:
    # 保存当前流的位置
    current_position = stream.tell()

    # 移动到流的末尾，获取流的总字符数
    stream.seek(0, 2)  # 2 表示从流的末尾开始计算偏移量
    total_size = stream.tell()

    # 恢复流的位置
    stream.seek(current_position)

    return total_size > MAX_CHAR_SIZE


class TeeStream:
    def __init__(self, *streams: TextIO) -> None:
        self.streams = streams

    def write(self, data: str) -> None:
        for stream in self.streams:
            # 如果是标准输出流/标准错误流则直接写入
            if not isinstance(stream, io.StringIO):
                stream.write(data)
            # 若超过最大字符数则不写入，避免内存占用过高
            elif not exceeds_max_size(stream=stream):
                stream.write(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def isatty(self) -> bool:
        return any(stream.isatty() for stream in self.streams)


def pytest_main_with_output(args: List[str], plugin: T) -> Tuple[str, str, int]:
    exit_code = 0
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    stdout_stream = TeeStream(sys.stdout, stdout_capture)
    stderr_stream = TeeStream(sys.stderr, stderr_capture)
    with contextlib.redirect_stdout(stdout_stream), contextlib.redirect_stderr(stderr_stream):  # type: ignore
        exit_code = pytest.main(args, plugins=[plugin])
    captured_stdout = stdout_capture.getvalue()
    captured_stderr = stderr_capture.getvalue()
    return captured_stdout, captured_stderr, int(exit_code)
