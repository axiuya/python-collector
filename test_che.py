import binascii
import json

from libs.binary_helper import bytes_to_binary
from libs.che_op import parse_packet, convert_to_udp, parse_file_head

if __name__ == '__main__':
    # with open('D:/develop/CHE/01000402-2020_05_29-09_49_45.CHE', 'rb+') as f:
    with open('E:/0000037E-2019_11_06-14_58_46.CHE', 'rb+') as f:
        file_head = parse_file_head(f.read(576))
        print(json.dumps(file_head))
        print('deviceId:', file_head['deviceId'])

        for i in range(350, 400, 1):
            f.seek(i * 576)
            data = f.read(576)
            p = parse_packet(data=data, device_id=file_head['deviceId'])
            print(i, json.dumps(p.__dict__))

        print('-----------------------------------------------------')

        data = f.read(576)
        p = parse_packet(data=data, device_id=file_head['deviceId'])
        print(json.dumps(p.__dict__))

        udp_data = convert_to_udp(device_id='01000403', src=data)
        print(udp_data.hex().upper())
        np = parse_packet(data=udp_data, device_id='01000403')
        print(json.dumps(np.__dict__))

        print(bytes_to_binary(binascii.unhexlify('01000403')))
