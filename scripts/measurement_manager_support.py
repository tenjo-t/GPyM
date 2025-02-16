"""
measurement_managerモジュールで利用するクラスの詰め合わせ
"""


import msvcrt
import os
import threading
import time
from enum import Flag, auto
from logging import getLogger
from multiprocessing import Lock, Manager, Process, Value
from pathlib import Path
from typing import List, Optional, Union

import plot
import pyperclip
from basedata import BaseData
from utility import MyException, ask_save_filename, get_date_text
from variables import USER_VARIABLES

logger = getLogger(__name__)


class MeasurementStep(Flag):
    """測定ステップ"""

    READY = auto()
    START = auto()
    UPDATE = auto()
    FINISH_MEASURE = auto()
    END = auto()
    AFTER = auto()

    AFTER_MEASUREMENT_ALL_STEPS = FINISH_MEASURE | END | AFTER
    MEASURING = UPDATE


class MeasurementState:
    """測定の状態を詰める

    Attributes
    ----------
    current_step: MeasurementStep
        現在のステップ
    """

    current_step: MeasurementStep = MeasurementStep.READY

    def has_finished_measurement(self) -> bool:
        return bool(self.current_step & MeasurementStep.AFTER_MEASUREMENT_ALL_STEPS)

    def is_measuring(self) -> bool:
        return bool(self.current_step & MeasurementStep.MEASURING)







class FileManager:  # ファイルの管理
    """ファイルの作成・書き込みを行う

    Attributes
    ----------

    filepath:str
        書き込んだファイルのパス
    delimiter:str
        区切り文字
    """

    class FileError(MyException):
        """ファイル関連のエラー"""

    class FileIO:
        """実際にファイルに書き込みをする部分"""
        __filepath=None
        def __init__(self,filepath) -> None:
            self.__filepath=filepath
            self.__file = open(filepath,"x",encoding="utf-8")

        def write(self,text) -> None:
            self.__file.write(text)
            self.__file.flush()

        def close(self):
            self.__file.close()
            self.__file=None

        @property
        def filepath(self) -> str:
            """ファイルのパス"""
            return self.__filepath

    __prewrite: str = ""
    delimiter: str = ","
    __fileIO:FileIO =None  

    @property
    def filepath(self) -> str:
        """ファイルのパス"""
        return self.__fileIO.filepath if self.__fileIO is not None else None

    def set_file(self,filepath=None):
        if filepath is None:
            self.__fileIO=FileManager.FileIO(filepath=ask_save_filename(filetypes=[("TEXT",".txt"),],defaultextension = "txt",initialdir=USER_VARIABLES.DATADIR,initialfile=get_date_text(),title="作成するファイル名を設定してください"))
        else:
            self.__fileIO=FileManager.FileIO(filepath=filepath)

        if self.__prewrite!="":
            self.__fileIO.write(self.__prewrite)

        pyperclip.copy(os.path.basename(self.__fileIO.filepath)) #ファイル名はクリップボードにコピーしておく


    def save(self, *args: Union[tuple, str]) -> None:
        """データ保存"""

        text = ""

        for data in args:
            if issubclass(type(data),BaseData) or isinstance(data, tuple) or data is list:
                text += self.delimiter.join(map(str, data))
            else:
                text += str(data)
            text += self.delimiter
        text = text[0:-1] + "\n"
        self.__fileIO.write(text)

    def write(self, text: str) -> None:
        """ファイルへの書き込み

        ファイルがまだ作成されていなければ別の場所に一次保存
        """
        if self.__fileIO is None:
            self.__prewrite += text
        else:
            self.__fileIO.write(text)

    def close(self) -> None:
        """ファイルを閉じる"""
        self.__fileIO.close()

    


class CommandReceiver:  # コマンドの入力を受け取るクラス
    """コマンドの入力を検知する

    Attributes
    ----------

    __comand: Optional[str]
        入力されたコマンド
        スレッド間で共有する
        コマンド入力がないときはNone

    __isfinish:bool
        測定の終了
    """

    __command: Optional[str] = None
    __measurement_state = None

    def __init__(self, measurement_state: MeasurementState) -> None:
        self.__measurement_state = measurement_state

    def initialize(self) -> None:
        """
        別スレッドで__command_receive_threadを実行
        """
        cmthr = threading.Thread(target=self.__command_receive_thread)
        cmthr.setDaemon(True)
        cmthr.start()

    def __command_receive_thread(self) -> None:  # 終了コマンドの入力待ち, これは別スレッドで動かす
        while True:
            if (
                msvcrt.kbhit() and self.__measurement_state.is_measuring()
            ):  # 入力が入って初めてinputが動くように(inputが動くとその間ループを抜けられないので)
                command = input()
                if command != "":
                    self.__command = command
                    logger.info("command:%s", self.__command)
                    while self.__command is not None:
                        time.sleep(0.1)
            elif self.__measurement_state.has_finished_measurement():
                break
            time.sleep(0.1)

    def get_command(self) -> str:
        """受け取ったコマンドを返す. なければNoneを返す"""
        command = self.__command
        self.__command = None
        return command


class PlotAgency:
    """
    グラフ描画用のプロセスを別に作成して, そのプロセスに対して
    プロットするデータを送信する.
    実際のプロットはplot.pyが行うのでこのクラスはデータを渡すところを担っている.

    Attributes
    ----------
    share_list : List[tupple]
        plot.pyと共有するリスト. これを使ってplot.py側にデータを送信する.

    __isfinish : Value
        これもplot.pyと共有。 測定の終了をplot.pyに伝える

    process_lock : Lock
        これもplot.pyと共有。 share_listへの書き込みを同時に行わないように

    plot_process: Process
        plot.pyを実行しているプロセス
    """

    class PlotAgentError(MyException):
        """プロット仲介クラス関連の例外クラス"""

    share_list: List[tuple[float, float, str]]
    __isfinish: Value
    process_lock: Lock
    plot_process: Process

    def __init__(self) -> None:
        self.set_plot_info()

    def run_plot_window(self) -> None:  # グラフと終了コマンド待ち処理を走らせる
        """SSRではマルチプロセスを用いて測定プロセスとは別のプロセスでグラフの描画を行う.

        Pythonのマルチプロセスでは必要な値はプロセスの作成時に渡しておかなくてはならないので､(例外あり)
        ここではマルチプロセスの起動と必要な引数の受け渡しを行う.
        """

        self.share_list = Manager().list()  # プロセス間で共有できるリスト
        self.__isfinish = Value("i", 0)  # 測定の終了を判断するためのint
        self.process_lock = Lock()  # 2つのプロセスで同時に同じデータを触らないようにする排他制御のキー
        # グラフ表示は別プロセスで実行する
        self.plot_process = Process(
            target=plot.start_plot_window,
            args=(self.share_list, self.__isfinish, self.process_lock, self.plot_info),
        )
        self.plot_process.daemon = True  # プロセスのデーモン化
        self.plot_process.start()  # マルチプロセス実行

    def set_plot_info(
        self,
        line=False,
        xlog=False,
        ylog=False,
        renew_interval=1,
        legend=False,
        flowwidth=0,
    ) -> None:  # プロット情報の入力
        """グラフ描画プロセスに渡す値はここで設定する.

        __plot_infoが辞書型なのはアンパックして引数に渡すため

        Parameter
        ---------

        line: bool
            プロットに線を引くかどうか

        xlog,ylog :bool
            対数軸にするかどうか

        renew_interval : float (>0)
            グラフの更新間隔(秒)

        legend : bool
            凡例をつけるか. (凡例の名前はlabelの値)

        flowwidth : float (>0)
            これが0より大きい値のとき. グラフの横軸は固定され､横にプロットが流れるようなグラフになる.
        """

        if type(line) is not bool:
            raise self.PlotAgentError("set_plot_infoの引数に問題があります : lineの値はboolです")
        if type(xlog) is not bool or type(ylog) is not bool:
            raise self.PlotAgentError("set_plot_infoの引数に問題があります : xlog,ylogの値はboolです")
        if type(legend) is not bool:
            raise self.PlotAgentError("set_plot_infoの引数に問題があります : legendの値はboolです")
        if type(flowwidth) is not float and type(flowwidth) is not int:
            raise self.PlotAgentError(
                "set_plot_infoの引数に問題があります : flowwidthの型はintかfloatです"
            )
        if flowwidth < 0:
            raise self.PlotAgentError(
                "set_plot_infoの引数に問題があります : flowwidthの値は0以上にする必要があります"
            )
        if type(renew_interval) is not float and type(renew_interval) is not int:
            raise self.PlotAgentError(
                "set_plot_infoの引数に問題があります : renew_intervalの型はintかfloatです"
            )
        if renew_interval < 0:
            raise self.PlotAgentError(
                "set_plot_infoの引数に問題があります : renew_intervalの型は0以上にする必要があります"
            )

        self.plot_info = {
            "line": line,
            "xlog": xlog,
            "ylog": ylog,
            "renew_interval": renew_interval,
            "legend": legend,
            "flowwidth": flowwidth,
        }

    def plot(self, x, y, label="default") -> None:
        """データをグラフ描画プロセスに渡す.

        labelが変わると色が変わる
        __share_listは測定プロセスとグラフ描画プロセスの橋渡しとなるリストでバッファーの役割をする

        Parameter
        ---------

        x,y : float
            プロットのx,y座標

        label : string or float
            プロットの識別ラベル.
            これが同じだと同じ色でプロットしたり､線を引き設定のときは線を引いたりする.
        """

        if self.is_plot_window_alive():
            data = (x, y, label)
            self.process_lock.acquire()  #   ロックをかけて別プロセスからアクセスできないようにする
            self.share_list.append(data)  # プロセス間で共有するリストにデータを追加
            self.process_lock.release()  # ロック解除

    def stop_renew_plot_window(self) -> None:
        """プロットウィンドウの更新を停止"""
        self.__isfinish.value = 1

    def close(self) -> None:
        """プロットウィンドウを閉じる"""
        self.plot_process.terminate()

    def is_plot_window_alive(self) -> bool:
        """self.plot_processが生きているかどうかを判定"""

        return self.plot_process.is_alive()

    def is_plot_window_forced_terminated(self) -> bool:
        """self.plot_processがバツボタンで強制終了されたかどうかを判定

        is_plot_window_aliveの逆に見えるが、not_run_plot_windowを実行した場合に挙動が異なる
        """
        return not self.plot_process.is_alive()

    class NoPlotAgency:
        """プロット無効状態のときにmeasurement.manager.plot_agencyにこのインスタンスを入れる"""

        def __init__(self) -> None:
            """グラフを表示しないモード"""

            def void(*args):
                """何も返さない関数"""

            def void_constant(value):
                """定数を返す関数を返す関数"""

                def void(*args):
                    """定数を返す関数"""
                    return value

                return void

            self.run_plot_window = void
            self.set_plot_info = void
            self.plot = void
            self.stop_renew_plot_window = void
            self.close = void
            self.is_plot_window_alive = void_constant(False)
            self.is_plot_window_forced_terminated = void_constant(False)
