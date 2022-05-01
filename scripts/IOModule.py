import os
import utilityModule as util
from typing import Union
import sys
from typing import Optional
import time
import threading
import msvcrt
from utilityModule import inputlog
import variables as vars

__logger=util.mklogger(__name__)


class FileManager(): #ファイルの管理
    """
    ファイルの作成・書き込みを行う

    Attributes
    ------------

    filepath:str 
        書き込んだファイルのパス
    filename:str
        ファイル名
    file
        ファイルのインスタンス
    
    """

    filepath:str
    filename:str
    file=None
    _user_label=""

    def create_file(self,filename:str,data_label:str,is_bunkatsu:bool)->None:
        self.name=filename
        """
        フォルダが無ければエラーを出し､あれば新規でファイルを作り､__savefileに代入
        """

        if not os.path.isdir(vars.DATADIR):#フォルダの存在確認
            raise util.create_error(vars.DATADIR+"のフォルダにアクセスしようとしましたが､存在しませんでした",__logger)
        

        if is_bunkatsu :
            self.path=vars.DATADIR+"\\"+ filename+".txt"
        else:
            nowdatadir=vars.DATADIR+"\\"+ filename
            os.mkdir(nowdatadir)
            self.path=nowdatadir+"\\"+ filename+".txt"
        

    
        

        self.file = open(self.path, 'x',encoding="utf-8") #ファイル作成

        file_label=self._user_label+data_label+"\n"
        self.file.write(file_label) #測定データのラベル書き込み

        self.file.flush() #書き込みを反映させる

    def save(self,data:Union[str,tuple]):

        if type(data) is not str and not isinstance(data, tuple):
            raise util.create_error(sys._getframe().f_code.co_name+": dataはタプル型､もしくはstring型でなければなりません",__logger)

        if type(data) is str:#文字列を入力したときにも一応対応
            self.file.write(data)#書き込み
        else:
            text=""
            for i in range(len(data)):#タプルの全要素をstringにして並べる
                if i == 0:
                    text+=str(data[0])
                else:
                    text+=","+str(data[i])
            text+="\n"#末尾に改行記号
            self.file.write(text)#書き込み
        self.file.flush()#反映. 

    def set_label(self,label:str)->None:
        if not label[-1]=="\n":#末尾に改行コードがついていなければくっつける
            label+="\n"
        self._user_label=self._user_label+label

    def close(self):
        self.file.close()

class CommandReceiver():#コマンドの入力を受け取るクラス


    """
    コマンドの入力を検知する
    """

    __command:Optional[str]=None
    __isfinish:bool=False

            
    def initialize(self):
        """
        別スレッドで__command_receive_threadを実行
        """
        cmthr=threading.Thread(target=self.__command_receive_thread)
        cmthr.setDaemon(True)
        cmthr.start()

    def __command_receive_thread(self) -> None:#終了コマンドの入力待ち, これは別スレッドで動かす
        while True:
            if msvcrt.kbhit() and not self.__isfinish: #入力が入って初めてinputが動くように(inputが動くとその間ループを抜けられないので)
                self.__command=inputlog()
                while self.__command is not None:
                    time.sleep(0.1)
            elif self.__isfinish:
                break
            time.sleep(0.1)
        
    def get_command(self) -> str: #受け取ったコマンドを返す。なければNoneを返す
        command=self.__command
        self.__command=None
        return command
    
    def close(self):
        self.__isfinish=True




from multiprocessing import Process, Lock, Manager,Value
import windowModule
from typing import List

class PlotAgency():


    share_list:List[tuple]
    is_finish:Value
    process_lock:Lock
    window_process:Process

    def run_plot_window(self):#グラフと終了コマンド待ち処理を走らせる
        """
        GPyMではマルチプロセスを用いて測定プロセスとは別のプロセスでグラフの描画を行う.

        Pythonのマルチプロセスでは必要な値はプロセスの作成時に渡しておかなくてはならないので､(例外あり)
        ここではマルチプロセスの起動と必要な引数の受け渡しを行う.
        """

        self.share_list=Manager().list()#プロセス間で共有できるリスト
        self.is_finish=Value("i",0)#測定の終了を判断するためのint
        self.process_lock=Lock()#2つのプロセスで同時に同じデータを触らないようにする排他制御のキー
        #グラフ表示は別プロセスで実行する
        self.window_process=Process(target=windowModule.exec,args=(self.share_list,self.is_finish,self.process_lock,self.plot_info))
        self.window_process.daemon=True#プロセスのデーモン化
        self.window_process.start()#マルチプロセス実行

    def set_plot_info(self,line=False,xlog=False,ylog=False,renew_interval=1,legend=False,flowwidth=0):#プロット情報の入力
        """
        グラフ描画プロセスに渡す値はここで設定する.
        __plot_infoが辞書型なのはアンパックして引数に渡すため

        Parameter
        __________________________

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
            raise util.create_error(sys._getframe().f_code.co_name+": lineの値はTrueかFalseです",__logger)
        if type(xlog) is not bool or type(ylog) is not bool:
            raise util.create_error(sys._getframe().f_code.co_name+": xlog,ylogの値はTrueかFalseです",__logger)
        if type(legend) is not bool :
            raise util.create_error(sys._getframe().f_code.co_name+": legendの値はTrueかFalseです",__logger)
        if type(flowwidth) is not float and type(flowwidth) is not int:
            raise util.create_error(sys._getframe().f_code.co_name+": flowwidthの型はintかfloatです",__logger)
        if flowwidth<0:
            raise util.create_error(sys._getframe().f_code.co_name+": flowwidthの値は0以上にする必要があります",__logger)
        if type(renew_interval) is not float and type(renew_interval) is not int:
            raise util.create_error(sys._getframe().f_code.co_name+": renew_intervalの型はintかfloatです",__logger)
        if renew_interval<0:
            raise util.create_error(sys._getframe().f_code.co_name+": renew_intervalの型は0以上にする必要があります",__logger)

        self.plot_info={"line":line,"xlog":xlog,"ylog":ylog,"renew_interval":renew_interval,"legend":legend,"flowwidth":flowwidth}


    def plot(self,x,y,label="default"):
        """
        データをグラフ描画プロセスに渡す. 
        labelが変わると色が変わる
        __share_listは測定プロセスとグラフ描画プロセスの橋渡しとなるリストでバッファーの役割をする


        Parameter
        __________________________

        x,y : float
            プロットのx,y座標

        label : string or float
            プロットの識別ラベル.
            これが同じだと同じ色でプロットしたり､線を引き設定のときは線を引いたりする.

        """

        data=(x,y,label)
        self.process_lock.acquire() #   ロックをかけて別プロセスからアクセスできないようにする
        self.share_list.append(data)# プロセス間で共有するリストにデータを追加
        self.process_lock.release()#ロック解除

    def stop_renew_plot_window(self):
        self.is_finish.value=1

    def close(self):
        self.window_process.terminate()


    def is_plot_window_alive(self)->bool:
        return self.window_process.is_alive()

    def not_run_plot_window(self):
        def void(*args):
            pass
        def voidbool(*args):
            return False
        self.run_plot_window=void
        self.set_plot_info=void
        self.plot=void
        self.stop_renew_plot_window=void
        self.close=void
        self.is_plot_window_alive=voidbool



    