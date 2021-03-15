"""2进制字符串"""
BINARY_STR = (
    "0000", "0001", "0010", "0011", "0100", "0101", "0110", "0111",
    "1000", "1001", "1010", "1011", "1100", "1101", "1110", "1111"
)


def bytes_to_number(data, start=0, size=0, big_endian=True, signed=False):
    """
    字节转为数值
    :param data: 数据
    :param start: 开始的位置
    :param size: 计算的长度，为0表示全部计算
    :param big_endian: 字节顺序，大端/小端
    :param signed: 是否为有符号数值
    :return: 返回计算后的数值
    """
    v = 0
    if size <= 0:
        size = int(len(data) - start)

    if big_endian:
        if signed and ((data[start] & 0b10000000) >> 7) == 1:
            for i in range(size):
                v <<= 8
                v |= ~data[start + i] & 0xFF
            v = ((-v) - 1)
        else:
            for i in range(size):
                v <<= 8
                v |= data[start + i] & 0xFF
    else:
        if signed and ((data[len(data) - 1] & 0b10000000) >> 7) == 1:
            for i in reversed(range(size)):
                v <<= 8
                v |= ~data[start + i] & 0xFF
            v = ((-v) - 1)
        else:
            for i in reversed(range(size)):
                v <<= 8
                v |= data[start + i] & 0xFF
    return int(v)


def number_to_bytes(num, byte_size, big_endian=True):
    """
    数值转换成字节数组
    :param num: 数值
    :param byte_size: 字节数量
    :param big_endian: 是否为大端字节序，默认为True
    :return: 返回转换后的字节数组
    """
    # 大端字节顺序：高位在前，低位在后  数值先高字节位移，后低字节
    # 小端字节顺序：低位在前，高位在后  数值先取低字节，后高字节依次右移
    array = bytearray([0] * int(byte_size))
    bits = int(byte_size * 8)
    for i in range(len(array)):
        if big_endian:
            array[i] = num >> ((bits - 8) - i * 8)
        else:
            array[i] = num >> (i * 8)
    return array


def bytes_to_binary(data, start=0, size=0, split=None, split_len=1):
    """
    将字节转换二进制字符串，size为0标识从开始的部分，其后的数据全部转换
    :param data: 字节数组
    :param start: 开始的位置
    :param size: 读取的长度
    :param split: 分隔符
    :param split_len: 分割的长度
    :return: 返回转换后的二进制字符串
    """
    if size == 0:
        size = len(data) - start
    strbuilder = []
    for i in range(size):
        # 高四位
        strbuilder.append(BINARY_STR[(data[i] & 0xF0) >> 4])
        # 低四位
        strbuilder.append(BINARY_STR[data[i] & 0x0F])
        if split is not None \
                and i % split_len == 0 \
                and 0 < i < len(data) - 1:
            strbuilder.append(split)

    return strbuilder


def copy_bytes(src, src_pos, dest, dest_pos, size):
    """拷贝字节数组"""
    for k in range(size):
        dest[dest_pos + k] = src[src_pos + k]
    return dest

# def int_to_float(value):
#     """
#     整数转换为浮点数
#     :param value: 数值
#     :return: 返回值
#     """
#     pass
