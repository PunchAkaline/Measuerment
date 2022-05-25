#!/usr/bin/python3
import argparse
import os
import pathlib
import sys
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pyvisa as visa
from matplotlib.lines import Line2D
from parse import search


def main():

    # コマンドライン引数の設定
    parser = argparse.ArgumentParser(prog='SimpleMeasure.py', add_help=True)
    parser.add_argument('wv_init', type=float, help='測定開始波長(nm)')
    parser.add_argument('wv_last', type=float, help='測定終了波長(nm)')
    parser.add_argument('wv_step', type=float, help='測定波長ステップ(nm)')
    parser.add_argument('-sw', '--scan_wait', type=float,
                        required=False, default=1, help='波長変化後の待機時間(秒)')
    parser.add_argument('-ls', '--laser', type=str, required=False,
                        default='TSL-710', help='レーザー: TSL-710 or TSL-510 or TSL-210F or TLB-6500')
    parser.add_argument('-lc', '--lockin', type=str, required=False,
                        default='LI5645', help='ロックイン: LI5645 (new) or LI5660 (old)')
    parser.add_argument('-dir', '--file_dir', type=str,
                        required=False, default='C:/Users/Takashi Asano/Measurement', help='測定結果を入れる大本のディレクトリ')
    parser.add_argument('-sn', '--sample_name', type=str,
                        required=False, default='test', help='サンプル名')
    parser.add_argument('-com', '--comment', type=str,
                        required=False, default='no_comment', help='コメント')
    parser.add_argument('-fh', '--file_header', type=str,
                        required=False, default='Drop', help='ファイル名の最初につける識別子')
    parser.add_argument('-ft', '--finetuning', action='store_true',
                        required=False,  help='ファインチューニングの時')
    parser.add_argument('-wm', '--wavemeas', action='store_true',
                        required=False,  help='波長測定を行う場合付与する．')
    parser.add_argument('-at', '--adaptive', type=float,
                        required=False, default=1e9, help='ファインチューニングkankaku')
    parser.add_argument('-pow', '--power', type=float,
                        required=False, default=1.0, help='Laser Power (mW)')
    parser.add_argument('-nom', '--no_measurement', action='store_true',
                        required=False,  help='no measurement, set laser parameters only')
    parser.add_argument('-off', '--laser_turn_off', action='store_true',
                        required=False,  help='turn off TSL-210')
    

    # コマンドライン引数の取得
    args = parser.parse_args()

    # GPIB通信コンストラクション
    devMan = Resources()
    # レーザー
    herald, laser_inst = devMan.getInstrument(args.laser)
    if laser_inst is not None:
        if args.laser=='TLB-6500':
            laser = TLB(laser_inst,args.laser)
        else:
            laser = TSL(laser_inst,args.laser)
            if args.laser=='TSL-210F':
                if args.laser_turn_off:
                    laser.turnOffLD()
                else:
                    laser.turnOnLD()
                    laser.setAPCmode()
                    laser.setPower(args.power)

    # ロックイン
    herald, lockin_inst = devMan.getInstrument(args.lockin)
    if lockin_inst is not None:
        lockin = Lockin(lockin_inst)
    # 波長計
    if args.wavemeas:
        wavelengthmeter = WavelengthMeter(
            devMan.rm.open_resource("GPIB0::7::INSTR"))

    # グラフ準備
    fig, ax = plt.subplots(1, 1, figsize=(8, 7))
    # 測定波長の値域設定
    if args.finetuning:
        offset = laser.readWavelength()
        ft_c = -0.5e-3  # [nm/fine-tuning step]
        init = args.wv_init * ft_c + offset
        last = args.wv_last * ft_c + offset

    else:
        init = args.wv_init
        last = args.wv_last

    min_wv = min(args.wv_init, args.wv_last)
    max_wv = max(args.wv_init, args.wv_last)

    lines = Line2D([], [], color='blue', marker='o', linestyle='-')
    ax.add_line(lines)
    # lines, = ax
    # 
    # .plot([min(init, last), 0], [min(init, last), 1e-6], 'bo-')

    ax.set_xlim(min(init, last), max(init, last))
    ax.set_ylim(0, 1)
    ax.set_xlabel('Wavelength (nm)')
    ax.set_ylabel('Intensity (V)')
    ax.grid
    plt.gca().yaxis.set_major_formatter(plt.FormatStrFormatter('%1.1e'))
    plt.gca().xaxis.get_major_formatter().set_useOffset(False)

    # 測定開始
    # 初期波長設定
    if args.finetuning:
        laser.setFinetuning(args.wv_init)
    else:
        laser.setWavelength(args.wv_init)
    time.sleep(2)
    # while laser.readWavelength()!=args.wv_init:
    #     time.sleep(0.1)

    # 補助パラメーター設定
    num_row =2 
    if args.finetuning:
        num_row += 1
    if args.wavemeas:
        num_row +=1
    
    spectrum = np.empty((0, num_row))

    # 測定開始
    print('Measurement Start!!')
    print('Please input ctrl-C to interrupt.')

    wv = args.wv_init
    while ((wv - min_wv >=0 and wv-max_wv <=0) and not args.no_measurement):
        try:
            # 波長
            if args.finetuning:
                laser.setFinetuning(wv)
                time.sleep(args.scan_wait)
                wl = laser.readFinetuning()

                # while wl != wv:
                #     time.sleep(0.1)
                #     wl = laser.readFinetuning()
                #     print(wv, wl)
                ft = wl
                wl = wl * (ft_c) + offset
                wl = round(wl, 5)

            else:
                laser.setWavelength(wv)
                time.sleep(args.scan_wait)
                wl = laser.readWavelength()

            # 波長計の読み取り値
            if args.wavemeas:
                wl2 = wavelengthmeter.readWavelength()[1]
                print(wl, wl2)
                # wl = round(wl,4)

            # ロックインからの強度
            intensity = lockin.fetchDataset()[0]

            # output data:
            output_data = [wl, intensity]
            if args.wavemeas:
                output_data += [wl2]
            if args.finetuning:
                output_data += [ft]

            output_data = np.array(output_data)
            spectrum = np.vstack((spectrum, output_data))

            lines.set_data(spectrum[:, 0], spectrum[:, 1])
            ax.set_ylim(0.0, np.amax(spectrum[:, 1]))
            plt.pause(0.001)

#            if intensity > args.adaptive:
#                wv += args.wv_step /5
#            else:
#                wv += args.wv_step

        except KeyboardInterrupt:
            print("Break Measurement!!")
            break

    print('Measurement Finished!!')

    # 測定結果.txtの保存先ディレクトリ構造
    if not args.no_measurement:
        components = [args.file_dir]
        filepath = getFilePath_YMD(components, args.file_header)
        comments = args.sample_name + ', ' + args.comment + '\n'
        #comments += 'laser_power {}\n'.format(laser.readPower())
        comments += 'lockin_range {}\n'.format(lockin.readRange())
        comments += 'lockin_freq {}\n'.format(lockin.readFreq())
        comments += 'lockin_timeconst {}\n'.format(lockin.readTimeconst())
        comments += 'scan_wait {}\n'.format(args.scan_wait)
        comments += 'wv_init {}, wv_last {} wv_step {}\n'.format(args.wv_init, args.wv_last, args.wv_step)
        np.savetxt(filepath, spectrum, header=comments)
        plt.savefig(filepath.with_suffix(".png"))
        print('File saved: {}'.format(str(filepath)))
    print('Please input ctrl-C to exit.')

    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            break
    plt.close()
    # plt.show()


def getFilePath_YMD(components, specified=''):
    '''
    リストcomponentsの要素をディレクトリとした階層におけるYYYYMMDD_no.txtというファイルのパスを返す
    たとえば `components = ['hoge', 'foo']`の場合
    hoge/foo/specifiedYYYYMMDD_no.txtというpathを返すことになる．
    リストの要素を名とするディレクトリが存在しなければ作成する．
    結構難しいことをやっているのでコード内にもコメントを書いておく．
    '''

    # componentsで規定されるディレクトリ構造の確認
    filepath = pathlib.Path('')
    for component in components:
        filepath /= pathlib.Path(component)
        if not filepath.exists():
            filepath.mkdir()

    # 今日の日付を取得して既存ファイル名の一覧を取得した後に，もっとも数字の大きいものを取り出す．
    todaysdate = datetime.today().date()
    str_date = '_{0:%Y%m%d}'.format(todaysdate)
    exist_files = sorted(filepath.glob(specified + str_date + '_*.txt'))

    if(len(exist_files) > 0):
        no = search('_{:d}.txt', exist_files[-1].name)[0]
    else:
        no = 0  # ファイルが存在しない場合のインデックスは0

    return filepath / pathlib.Path(specified + str_date + '_{0:02d}.txt'.format(no + 1))


class Resources:
    '''
    通名とGPIBアドレス間をつなぎ，プロセス中の機器を管理するインターフェースクラス
    '''
    GPIB_ADDRESSES = {'TSL-710': 'GPIB0::17::INSTR',
                      'TSL-510': 'GPIB0::12::INSTR',
                      'TLB-6500': 'GPIB0::11::INSTR',
                      'LI5660': 'GPIB0::6::INSTR',
                      'LI5645': 'GPIB0::2::INSTR',
                      'TSL-210F': 'GPIB0::11::INSTR'
                      }
    # デバイスを区別する必要がないので，LOCKINは同じgpibアドレスを割り当てることにする．
    # 同時に両方使う場合は別のアドレスを割り当てる．

    def __init__(self):
        self.rm = visa.ResourceManager()
        self.instruments = {}  # 呼び出したinstrumentsをリストアップしておく．

    def __repr__(self):
        return self.rm.list_resources()

    def checkIDN(self):
        for resource_name in self.rm.list_resources():
            instrument = self.rm.open_resource(resource_name)
            print("ID: {}, Instrument: {}\n".format(
                resource_name, instrument.query('*IDN?')))

    def getInstrument(self, key):
        if not Resources.GPIB_ADDRESSES[key] in self.rm.list_resources():
            print('{} is not active; Please check the device is tured on or a gpib cable is properly connected '.format(key))
            return False, None

        elif key in self.instruments.keys():
            return True, None

        else:
            inst = self.rm.open_resource(Resources.GPIB_ADDRESSES[key])
            self.instruments[key] = inst
            return True, inst


class Instrument:

    def __init__(self, instrument):
        self.inst = instrument

    def __repr__(self):
        print('IDN: {}'.format(self.query('*IDN?')))

    def write(self, command):
        # パラメーターの設定
        self.inst.write(command)

    def _write(self, command):
        # パラメーターの設定
        self.inst.write(command)

        while self.query('*ORC?')[0] == '0':
            # 動作完了まで待機
            print("Please Wait...")
            time.sleep(0.1)

        print("Done.")

    def read(self):
        return self.inst.read()

    def query(self, command):
        return self.inst.query(command)

    def readvalue(self, command):
        # ACII型の返り値をparseしてArrayで返す
        return self.inst.query_ascii_values(command)


class TSL(Instrument):
    '''
    レーザーのドライバークラス
    多分Santec以外にも使えるが，当面TSL-510, -710での使用を考え，このようなクラス名にした．
    '''

    def __init__(self, instrument, laser, finemode=False):
        super().__init__(instrument)
        if laser != 'TSL-210F':
            self.wl_precision = 4   # nm単位で小数第何位までか: -log(0.1pm/1nm) = 4
            self.wl_min = self.readvalue(':WAV:MIN?')[0]
            self.wl_max = self.readvalue(':WAV:MAX?')[0]
            self.pw_min = self.readvalue(':POW:MIN?')[0]
            self.pw_max = self.readvalue(':POW:MAX?')[0]
            self.write(':WAV:UNIT 0')  # 波長の単位をnmに設定
            self.write(':POW:UNIT 1')  # 光パワーの単位をmWに設定
        else:
            self.wl_precision = 2   # nm単位で小数第何位までか: -log(0.1pm/1nm) = 4
            self.wl_min = 1440.0
            self.wl_max = 1520.0
            self.pw_min = 0.00
            self.pw_max = 3.00
            self.wavelength=0.0

        self.laser=laser

    def setWavelength(self, value):
        if self.laser=='TSL-210F':
            self.write('WA{0:4.2f}'.format(
                np.clip(value, self.wl_min, self.wl_max)))
            self.wavelength=value
        else: 
            self.write(':WAV {0:4.4f}'.format(
                np.clip(value, self.wl_min, self.wl_max)))

    def setPower(self, value):
        if self.laser == 'TSL-210F':
            self.write('LP{0:3.2f}'.format(
                np.clip(value, self.pw_min, self.pw_max)))
            self.laserpower=value
        else:
            self.write(':POW {0:2.3f}'.format(
                np.clip(value, self.pw_min, self.pw_max)))

    def setFinetuning(self, value):
        value = np.clip(value, -100.0, 100.0)
        self.write(':WAV:FIN {0:3.2f}'.format(value))

    def setAtt(self, value):
        value = np.clip(value, 0.0, 30.0)
        self.write(':POW:ATT {0:2.2f}'.format)

    def openShutter(self):
        return self.write(':POW:SHUT 0')

    def closeShutter(self):
        return self.write(':POW:SHUT 1')

    def turnOnLD(self):
        if self.laser == 'TSL-210F':
            self.write('LO')
            while(self.readvalue('SU')[0]>0.0):
                time.sleep(0.5)
                print(self.readvalue('SU')[0])
        else:
            print("This command is for TSL-210F")

    def turnOffLD(self):
        if self.laser == 'TSL-210F':
            self.write('LF')
            while(self.readvalue('SU')[0] < 0.0):
                time.sleep(0.5)
                print(self.readvalue('SU')[0])
        else:
            print("This command is for TSL-210F")

    def setAPCmode(self):
        if self.laser == 'TSL-210F':
            return self.write('AF')
        else:
            print("This command is for TSL-210F")

    def readPower(self):
        if self.laser == 'TSL-210F':
            return self.laserpower
        else:
            return self.readvalue(':POW:ACT?')[0]

    def readWavelength(self):
        if self.laser == 'TSL-210F':
            return self.wavelength
        else:
            return self.readvalue(':WAV?')[0]

    def readFinetuning(self):
        return self.readvalue(':WAV:FIN?')[0]


class TLB(Instrument):
    '''
    レーザーのドライバークラス
    TLB-6500用．
    '''

    def __init__(self, instrument, finemode=False):
        super().__init__(instrument)
        self.wl_min = self.readvalue(':WAVE MIN?')[0]
        self.wl_max = self.readvalue(':WAVE MAX?')[0]

    def readWavelength(self):
        value="OK"
        while value=="OK":
            value=self.query(':WAVE ?')
        return float(value)
        

    def setWavelength(self, value):     
        self.write(':WAVE {0:4.4f}'.format(
            np.clip(value, self.wl_min, self.wl_max)))
        self.read()



class WavelengthMeter(Instrument):

    def __init__(self, instrument):
        super().__init__(instrument)

    def readWavelength(self):
        val = self.readvalue(":MEAS:ARR:POW:WAV?")
        return val


class Lockin(Instrument):

    def __init__(self, instrument):
        super().__init__(instrument)
        self.inst.write(':CALC1:FORM MLIN;FORM ASC')  # 測定パラメーターを指定．

    def fetchDataset(self):
        values = super().readvalue(':FETC?')
        return(values)
#        if(values[0] == 0):
#            return values[1:]
#        else:
#            print("STATUS: ERROR: {}".format(values[0]))
#            return [0, ]

    def readFreq(self):
        values = super().readvalue(':FREQ?')
        return(values[0])

    def readRange(self):
        values = super().readvalue(':VOLT:AC:RANG?')
        return(values[0])

    def readTimeconst(self):
        values = super().readvalue(':FILT:TCON?')
        return(values[0])

    def showOutputParameters(self):
        print("DATA1: {}".format(self.query(':CALC1:FORM?')))
        print("DATA2: {}".format(self.query(':CALC2:FORM?')))
        print("DATA3: {}".format(self.query(':CALC3:FORM?')))
        print("DATA4: {}".format(self.query(':CALC4:FORM?')))


if __name__ == '__main__':
    main()
