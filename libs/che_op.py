import binascii
import math
from enum import Enum

from libs.binary_helper import bytes_to_number, number_to_bytes, copy_bytes

"""包头"""
_HEAD = (0x55, 0xAA)
"""波形高位需要相 & 的位"""
_WAVE_BIT = (0b00000011, 0b00001100, 0b00110000, 0b11000000)
"""移位"""
_MOVE = (0, 2, 4, 6)

"""电池电量"""
_battery_level_cache = dict()
"""体温序号缓存"""
_temperature_sn_cache = dict()


class BatteryLevel(Enum):
    """电池电量"""
    COLLECTOR_INNER = 0  # 采集器内部电池
    COLLECTOR_OUTER = 1  # 采集器外部电池
    THERMOMETER = 2  # 体温计电池
    OXIMETER = 3  # 血氧计电池
    SPHYGMOMANOMETER = 4  # 血压计电池
    FLOWMETER = 5  # 流速仪电池


def is_head(data, start=0):
    """是否为数据头"""
    return data[start] == _HEAD[0] and data[start + 1] == _HEAD[1]


def length(data, start=2):
    """长度，除包头外的剩余字节"""
    return bytes_to_number(data, start, 2)


def is_collector_length(data, start=2):
    """是否为采集器的数据长度"""
    return (2 + length(data, start)) == len(data)


def check_sum(data, start=0):
    """计算校验和"""
    v = 0
    for i in range(start, min(start + 545 - 1, len(data) - 1)):
        v += data[i]
    return v & 0xFF


def verify(data, start=0, sum=False):
    """验证UDP数据"""
    sum_result = True
    if sum:
        sum_result = check_sum(data, start) == data[min(start + 545 - 1, len(data) - 1)]
    return is_head(data, start) \
           and is_collector_length(data, start + 2) \
           and sum_result


def parse_device_id(data, start=4, size=4):
    """解析设备ID"""
    return data[start, start + size].hex()


def parse_packet_type(data, start=8):
    """解析数据包类型"""
    return data[start] & 0xFF


def parse_file_head(data):
    """
    解析文件头
    :param data: 文件头的字节数据
    :return: 返回解析的对象
    """
    array = data.decode('UTF-8').rstrip().split('_')
    return dict(manufacturer=array[0],  # 厂商名
                deviceName=array[1],  # 设备名称
                firmwareVersion=array[3].split(':')[1],  # 固件版本
                hardwareVersion=array[4].split(':')[1],  # 硬件版本
                deviceId=array[5].split(':')[1],  # 设备ID
                resp=array[6].split(':')[1],  # 呼吸位数和采样率
                ecg=array[7].split(':')[1],  # 心电位数和采样率
                axes=array[8].split(':')[1],  # 三轴位数和采样率
                spo2=array[9].split(':')[1],  # 血氧位数和采样率
                )


def parse_packet_sn(data, start=0):
    """解析包序号"""
    return bytes_to_number(data, start, 4)


def parse_time(data, start=4, size=4):
    """解析时间"""
    time = bytes_to_number(data, start, 4) * 1000
    if size == 6:
        time += bytes_to_number[data, start + 4, 2]
    return time


def right_move(b, move):
    """
    右移
    :param b: 字节
    :param move: 右移的位数
    :return: 返回右移的结果
    """
    value = b
    if move == 0:
        value = (b & 0b00000001)
    elif move == 1:
        value = (b & 0b00000010)
    elif move == 2:
        value = (b & 0b00000100)
    elif move == 3:
        value = (b & 0b00001000)
    elif move == 4:
        value = (b & 0b00010000)
    elif move == 5:
        value = (b & 0b00100000)
    elif move == 6:
        value = (b & 0b01000000)
    elif move == 7:
        value = (b & 0b10000000)
    return value >> move


def parse_packet(data, start=0, device_id=None):
    """
    解析数据包
    :param data: 数据
    :param start: 开始的位置
    :param device_id: 设备ID
    :return: 返回解析后的包对象
    """
    if verify(data=data, start=start, sum=False):
        start = start + 9

    pkt = Packet()
    pkt.deviceId = device_id
    pkt.deviceCode = 0
    if device_id is not None and isinstance(device_id, str):
        pkt.deviceCode = bytes_to_number(binascii.unhexlify(device_id))
    # 包序号: (0 ~ 3)
    pkt.packetSn = parse_packet_sn(data, start)
    # 获取设备时间: (4 ~ 9)
    pkt.time = parse_time(data, start + 4)

    # 解析波形数据
    # 胸呼吸波形: (10 ~ 59) => 50
    pkt.rawChestRespList = parse_array(data, start + 10, start + 60, 2)
    # 腹呼吸波形: (60 ~ 109) => 50
    pkt.rawAbdominalRespList = parse_array(data, start + 60, start + 110, 2)
    # 心电波形: (110 ~ 361) => [4 * (50 + 13) = 252]
    pkt.ecgList = parse_wave(4, 50, 13, data, start + 110)
    # 加速度波形数据 (362, 456) => 96
    # X轴 (362, 393) => [25 + 7 = 32]
    pkt.xList = parse_wave(1, 25, 7, data, start + 362)
    # Y轴 (394, 425) => [25 + 7 = 32]
    pkt.yList = parse_wave(1, 25, 7, data, start + 394)
    # Z轴 (426, 457) => [25 + 7 = 32]
    pkt.zList = parse_wave(1, 25, 7, data, start + 426)
    # 血氧波形: (458, 507) => 50
    pkt.spo2List = parse_array(data, start + 458, start + 508, 1)

    # 包含流速仪数据: (544, 668)
    pkt.flowmeter = (data[start + 8] & 0xFF) == 0xF3
    if pkt.flowmeter:
        # 流速仪第0组数据 (544, 549]
        # 25组，
        # 第一组:
        # 吹气或呼吸(0/1)，1个字节(544)
        # 实时流速值 ml/s，2个字节(545, 547]
        # 实时容积 ml，2个字节(547, 549]
        pkt.breathList = [0] * 25
        pkt.flowVelocityList = [0] * 25
        pkt.volumeList = [0] * 25
        j = start + 544
        for i in range(25):
            pkt.breathList[i] = data[i + j] & 0xFF
            pkt.flowVelocityList[i] = bytes_to_number([data[i + j + 1], data[i + j + 2]])
            pkt.volumeList[i] = bytes_to_number([data[i + j + 3], data[i + j + 4]])
            j += 5

    # 体温时间: (508, 511)
    pkt.temperatureTime = parse_time(data, 508 + start, 4) * 1000

    # 参数高位：(512)
    param_high = data[512 + start]
    # 设备功耗过高标志       (5)
    pkt.deviceOverload = right_move(param_high, 5)
    # 胸呼吸连接标志( 0 连接 (6)
    pkt.respConnState = right_move(param_high, 6)
    # 腹呼吸连接标志( 0 连接 (7)
    pkt.abdominalConnState = right_move(param_high, 7)
    # 血氧信号强度(513)
    pkt.spo2Signal = data[513 + start]
    # 胸呼吸系数(514)
    pkt.respRatio = data[513 + start]
    # 腹呼吸系数(515)
    pkt.abdominalRatio = (data[515 + start] & 0xff)
    # 体温(516)
    pkt.temperature = ((right_move(param_high, 2) << 8) | (data[516 + start] & 0xFF))
    # 血氧饱和度(517)
    pkt.spo2 = data[517 + start]

    ## 设备状态: (518)   ... 0 为正常; / 1 为告警;
    # 开机标志在开机第一包数据该位置 1, 其他数据包该位置 0;
    # 时间设置标志开机置 1,在接收到时间设备指令后置 0
    device_state = data[518 + start]
    # 心电导联脱落状态
    pkt.ecgConnState = right_move(device_state, 0)
    # 血氧探头脱落标志
    pkt.spo2ProbeConnState = right_move(device_state, 1)
    # 体温连接断开标志
    pkt.temperatureConnState = right_move(device_state, 2)
    # 血氧连接断开标志
    pkt.spo2ConnState = right_move(device_state, 3)
    # 血压连接断开标志
    pkt.elecMmhgConnState = right_move(device_state, 4)
    # 流速仪连接断开标志
    pkt.flowmeterConnState = right_move(device_state, 5)
    # 时间设置标志
    pkt.calibrationTime = right_move(device_state, 6)
    # 开机标志
    pkt.powerOn = right_move(device_state, 7)

    # 电量提示：(519)   0 为正常; 1 为告警
    battery_hint = data[519 + start]
    # 外部电池电量低
    pkt.deviceOuterBatteryAlarm = right_move(battery_hint, 0)
    # 蓝牙体温计电量低
    pkt.temperatureBatteryAlarm = right_move(battery_hint, 1)
    # 蓝牙血氧电量低
    pkt.spo2BatteryAlarm = right_move(battery_hint, 2)
    # 蓝牙血压计电量低
    pkt.elecMmhgBatteryAlarm = right_move(battery_hint, 3)
    # 流速仪电量低
    pkt.flowmeterBatteryAlarm = right_move(battery_hint, 4)

    # 状态开关: (520)，0为关; 1为开
    switch_state = data[520 + start]
    # 蓝牙连接断开蓝闪
    pkt.bluetoothConnSwitch = right_move(switch_state, 0)
    # 锂电池电量低绿闪
    pkt.batteryLowLightSwitch = right_move(switch_state, 1)
    # 锂电池电量低震动
    pkt.batteryLowShockSwitch = right_move(switch_state, 2)
    # 蓝牙设备电量低绿闪
    pkt.bluetoothLightSwitch = right_move(switch_state, 3)
    # 蓝牙体温计开关位
    pkt.temperatureSwitch = right_move(switch_state, 4)
    # 蓝牙血氧计开关位
    pkt.spo2Switch = right_move(switch_state, 5)
    # 蓝牙血压计开关位
    pkt.elecMmhgSwitch = right_move(switch_state, 6)
    # 蓝牙流速仪开关位
    pkt.flowmeterSwitch = right_move(switch_state, 7)

    # 电量: (521)
    battery_type = BatteryLevel(data[521 + start])
    battery = _battery_level_cache.get(device_id)
    if battery is None:
        battery = dict()
        _battery_level_cache[device_id] = battery
    if battery_type != BatteryLevel.COLLECTOR_INNER and battery_type != BatteryLevel.COLLECTOR_OUTER:
        battery[battery_type.name] = data[522 + start] & 0xFF
    else:
        power = math.floor(((((data[522 + start] & 0xFF) - 15) * 5 + 3200 - 3300) / (4050 - 3300)) * 100)
        battery[battery_type.name] = max(min(power, 100), 0)
    # 0：内部电池
    pkt.deviceBattery = battery.get(BatteryLevel.COLLECTOR_INNER.name, None)
    # 1：外部电池
    pkt.deviceOuterBattery = battery.get(BatteryLevel.COLLECTOR_OUTER.name, None)
    # 2：体温计电池
    pkt.temperatureBattery = battery.get(BatteryLevel.THERMOMETER.name, None)
    # 3：血氧计电池
    pkt.spo2Battery = battery.get(BatteryLevel.OXIMETER.name, None)
    # 4：血压计电池
    pkt.elecMmhgBattery = battery.get(BatteryLevel.SPHYGMOMANOMETER.name, None)
    # 5：流速仪
    pkt.flowmeterBattery = battery.get(BatteryLevel.FLOWMETER.name, None)

    # WiFi信号强度(523)
    pkt.wifiSignal = -(data[523 + start] & 0xFF)
    # 脉率 (524)
    pkt.pulseRate = ((right_move(param_high, 1) << 8) | (data[524 + start] & 0xFF))

    # AP MAC (525, 529)
    ap_mac = data[525 + start:525 + start + 5]

    if device_id is not None and device_id.startswith('11'):
        # 体温数据
        temperature_sn = ap_mac[2] & 0xFF
        old_temperature_sn = _temperature_sn_cache.get(device_id)
        pkt.carepatchSn = temperature_sn
        if old_temperature_sn is not None:
            if temperature_sn != old_temperature_sn:
                temperature = (((ap_mac[0] & 0xFF) << 8) | (ap_mac[1] & 0xFF))
                pkt.carepatchTemperature(temperature)
                _temperature_sn_cache[device_id] = temperature_sn
            else:
                pkt.carepatchTemperature = None
        else:
            pkt.carepatchTemperature = None
            _temperature_sn_cache[device_id] = temperature_sn
        pkt.setTemperature = 0
    else:
        pkt.apMac = ap_mac.hex()

    # 电池电量格数
    pkt.batteryLevelGridCount = data[534 + start] & 0xFF

    # 版本号 (530)
    version = data[530 + start]
    if version != 0:
        # 高位
        high = (version & 0b11100000) >> 5
        # 中位
        middle = (version & 0b00011100) >> 2
        # 低位
        low = version & 0b00000011
        # 固件版本
        pkt.versionCode = (high << 5) | (middle << 2) | low
        pkt.versionName = "{0}.{1}.{2}".format(high, middle, low)

    return pkt


def parse_array(data, start, end, byte_size):
    """解析数组"""
    arr = [0] * int((end - start) / byte_size)
    j = start
    for i in range(len(arr)):
        if byte_size == 1:
            arr[i] = data[j + 1] & 0xFF
        else:
            arr[i] = bytes_to_number(data[j:j + byte_size])
        j += byte_size
    return arr


def parse_wave(group, wave_len, high_len, data, start):
    """解析波形数组"""
    arr = [0] * int(wave_len * group)
    i = 0
    for n in range(group):
        for j in range(wave_len):
            arr[i] = calculate(wave_len, high_len, data, start, n, j)
            i += 1
    return arr


def calculate(wave_len, high_len, data, start, group, index):
    # 数据范围是“左开右闭”，以心电波形数据为例，其他同理
    # ============================================
    # 心电波形: (119, 371] == >: 252
    # ============================================
    # 心电波形1(高位)(119, 132] == >: 13
    # 心电波形1(低位)(132, 182] == >: 50
    # ============================================
    # 心电波形2(高位)   (182, 195]   ==>: 13
    # 心电波形2(低位)   (195, 245]   ==>: 50
    # ============================================
    # 心电波形3(高位)   (245, 258]   ==>: 13
    # 心电波形3(低位)   (258, 308]   ==>: 50
    # ============================================
    # 心电波形4(高位)   (308, 321]   ==>: 13
    # 心电波形4(低位)   (321, 371]   ==>: 50
    # ============================================
    # 4 * 63 ==>: 252
    # ============================================
    # 1个字节有8位
    # 每个波形的高位占2两位，如下标为119的字节值，8位分别为(132 ~ 136] 4个波形提供高位
    # ============================================
    # 以波形1为例：(119, 182]
    # 假如下标119的值为：55，即：‭0011 0111‬，第0个波形值取(0, 2]的2位(11)
    # 假如下标119的值为：55，即：‭0011 0111‬，第1个波形值取(2, 4]的2位(01)
    # 假如下标119的值为：55，即：‭0011 0111‬，第2个波形值取(4, 6]的2位(11)
    # 假如下标119的值为：55，即：‭0011 0111‬，第3个波形值取(6, 8]的2位(00)

    # 则，(((data[119] & (0000 0011)) >>> 0) << 8) | (data[132] & 0xFF)
    # 则，(((data[119] & (0000 1100)) >>> 2) << 8) | (data[133] & 0xFF)
    # 则，(((data[119] & (0011 0000)) >>> 4) << 8) | (data[134] & 0xFF)
    # 则，(((data[119] & (1100 0000)) >>> 6) << 8) | (data[135] & 0xFF)

    # 共有4组，每组占63个字节，n记录是第几组，假如第0组的第9个值，
    # 即，
    # 高位为：data[(n * 63) + (i / 4) + start]  ==>: data[(0 * 63) + (8 / 4) + 119] = data[121]
    # (data[121] & WAVE_BIT[i % 4]) >>> MOVE[i % 4]
    #
    # 低位为：data[(n * 63) + 13 + start]  ==>: data[(0 * 63) + 13 + 119] = data[132]
    # (data[132] & 0xFF)

    # 高位 | 低位  ==> 波形值

    size = wave_len + high_len
    high = ((((data[group * size + int(index / 4) + start] & 0xFF) & _WAVE_BIT[index % 4]) >> _MOVE[index % 4]) << 8)
    low = (data[group * size + high_len + index + start] & 0xFF)
    return high | low


class Packet:
    """解析后的数据包"""
    pass


def convert_to_udp(device_id, src, start=0, packet_sn=0, time=0):
    """
    转换成UDP数据包
    :param device_id: 设备ID，字节数组或字符串
    :param src: 数据(576字节)
    :param start: 开始读取的位置
    :param packet_sn: 包序号
    :param time: 时间
    :return: 返回转换后的UDP数据包
    """
    data = bytearray([0] * 545)
    # 包头
    data[0] = 0x55
    data[1] = 0xAA
    # 长度, 543
    data[2] = 0x02
    data[3] = 0x1F

    # 拷贝设备ID, 4 ~ 7
    # device_id =
    if isinstance(device_id, str):
        device_id = binascii.unhexlify(device_id)
    copy_bytes(device_id, 0, data, 4, 4)

    # 类型
    data[8] = 0x03

    # len: 2(head) + 2(length) + 4(deviceId) + 1(type) + 1(checkSum)
    copy_bytes(src, start, data, 9, min(535, len(src) - start))

    if packet_sn > 0:
        # 包序号
        copy_bytes(number_to_bytes(packet_sn, 4), 0, data, 9, 4)

    if time > 0:
        # 修改时间
        copy_bytes(number_to_bytes(int(time / 1000), 4), 0, data, 13, 4)

    # 校验和
    data[len(data) - 1] = check_sum(data)

    return data
