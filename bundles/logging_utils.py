import json
import logging


class JsonFormatter(logging.Formatter):
    """One JSON object per line, ready for Datadog / any log shipper."""

    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
            **getattr(record, "data", {}),
        }
        return json.dumps(payload)
