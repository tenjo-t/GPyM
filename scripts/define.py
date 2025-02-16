"""定義ファイルの取得や読み込みなど"""
from logging import getLogger
from pathlib import Path
from typing import Optional

from utility import MyException, ask_open_filename, get_encode_type
from variables import SHARED_VARIABLES, USER_VARIABLES

logger = getLogger(__name__)


class DefineFileError(MyException):
    """定義ファイル関係のエラー"""


def get_deffile() -> Path:
    """定義ファイルのパスの取得"""
    # 前回の定義ファルのパスが保存されているファイル
    path_deffilepath = SHARED_VARIABLES.TEMPDIR / "deffilepath"
    path_deffilepath.touch()

    # 前回の定義ファイルのフォルダを開いて定義ファイル選択画面へ
    predefdir: Optional[str] = None
    predeffilename = None
    predefpath = Path(path_deffilepath.read_text(encoding="utf-8"))
    if predefpath.is_file():
        predefdir = str(predefpath.parent)
        predeffilename = predefpath.name

    print("定義ファイル選択...")
    defpath = ask_open_filename(
        filetypes=[("定義ファイル", "*.def")],
        title="定義ファイルを選んでください",
        initialdir=predefdir,
        initialfile=predeffilename,
    )

    if defpath.is_file():
        # 今回の定義ファイルのパスを保存
        path_deffilepath.write_text(str(defpath), encoding="utf-8")

    return defpath


def read_deffile() -> None:
    """定義ファイルを読み込んで各フォルダのパスを取得"""
    path_deffile = get_deffile()
    logger.info("define file:%s", path_deffile.stem)

    datadir = None
    macrodir = None
    tempdir = None

    with path_deffile.open(mode="r", encoding=get_encode_type(path_deffile)) as f:
        # ファイルの中身を1行ずつ見ていく
        for l in f:
            # スペース･改行文字の削除
            l = "".join(l.split())
            if l.startswith("DATADIR="):
                # "DATADIR="の後ろの文字列を取得
                datadir = Path(l[8:])
            elif l.startswith("TMPDIR="):
                tempdir = Path(l[7:])
            elif l.startswith("MACRODIR="):
                macrodir = Path(l[9:])

    # 最後まで見てDATADIRが無ければエラー表示
    if datadir is None:
        raise DefineFileError("定義ファイルにDATADIRの定義がありません")
    # 相対パスなら定義ファイルからの絶対パスに変換
    if not datadir.is_absolute():
        datadir = path_deffile.parent / datadir
    # データフォルダが存在しなければエラー
    if not datadir.is_dir():
        raise DefineFileError(f"{datadir}は定義ファイルに設定されていますが存在しません")

    if tempdir is None:
        raise DefineFileError("定義ファイルにTMPDIRの定義がありません")
    if not tempdir.is_absolute():
        tempdir = path_deffile.parent / tempdir
    if not tempdir.is_dir():
        raise DefineFileError(f"{tempdir}は定義ファイルに設定されていますが存在しません")

    if macrodir is None:
        logger.warning("you can set MACRODIR in your define file")
    else:
        if not macrodir.is_absolute():
            macrodir = path_deffile.parent / macrodir
        if not macrodir.is_dir():
            logger.warning("%sは定義ファイルに設定されていますが存在しません", macrodir)
            macrodir = None

    # TODO (sakakibara): Use pathlib
    USER_VARIABLES.DATADIR = datadir
    USER_VARIABLES.TEMPDIR = tempdir
    USER_VARIABLES.MACRODIR = macrodir
