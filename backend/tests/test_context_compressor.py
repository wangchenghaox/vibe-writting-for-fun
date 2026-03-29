import pytest
from app.agent.context_compressor import ContextCompressor


def test_should_compress():
    compressor = ContextCompressor(max_tokens=1000, compress_threshold=0.7)

    # 少量消息不需要压缩
    messages = [{"role": "user", "content": "hello"}]
    assert not compressor.should_compress(messages)

    # 大量消息需要压缩
    large_messages = [{"role": "user", "content": "x" * 1000} for _ in range(100)]
    assert compressor.should_compress(large_messages)


def test_compress():
    compressor = ContextCompressor()

    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "resp1"},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "resp2"},
    ]

    compressed = compressor.compress(messages)

    # 应该保留system消息
    assert any(m["role"] == "system" for m in compressed)
    # 压缩后消息数量应该减少
    assert len(compressed) <= len(messages)
