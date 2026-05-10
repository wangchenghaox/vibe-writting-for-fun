from .openai_provider import OpenAICompatibleProvider


class KimiProvider(OpenAICompatibleProvider):
    def _prepare_messages(self, messages):
        return [
            {key: value for key, value in msg.items() if key != "reasoning_blocks"}
            for msg in messages
        ]

    def _apply_thinking_options(self, kwargs):
        if self.thinking_config.enabled:
            thinking = {"type": "enabled"}
            if self.thinking_config.keep:
                thinking["keep"] = self.thinking_config.keep
        else:
            thinking = {"type": "disabled"}
        kwargs["extra_body"] = {"thinking": thinking}
