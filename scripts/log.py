"""ログ出力関係"""
import json
from datetime import datetime
from logging import INFO, Formatter, config, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path

from variables import SHARED_VARIABLES

logger = getLogger(__name__)


def log(text: str) -> None:
    """ユーザー用に簡易ログ出力を提供"""
    logger.info(text)


def setlog() -> None:
    """ログファイルのセット"""

    with (SHARED_VARIABLES.SSR_SCRIPTSDIR / "log_config.json").open(
        mode="r", encoding="utf-8"
    ) as f:
        conf = json.load(f)

        now = datetime.now()

        # 月ごとに新しいファイルにログを書き出す
        conf["handlers"]["sharedFileHandler"]["filename"] = str(
            SHARED_VARIABLES.LOGDIR / f"{now.year}-{now.month}.log"
        )

        config.dictConfig(conf)


def set_user_log(path: str) -> None:
    """ユーザーフォルダ内にもログファイル書き出し"""
    path = Path(path) / "log.txt"
    handler = RotatingFileHandler(
        filename=path,
        encoding="utf-8",
        maxBytes=1024 * 100,
    )
    fmt = Formatter(
        "[%(asctime)s] [%(levelname)8s] [%(filename)s:%(lineno)s %(funcName)s]  %(message)s"
    )

    handler.setLevel(INFO)
    handler.setFormatter(fmt)
    getLogger().addHandler(handler)
