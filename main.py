import base64
import random
import time
import requests
import json
import configparser
import os
from typing import List, Dict
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT, SM4_DECRYPT
import sys
import gmssl.sm2 as sm2
from base64 import b64encode, b64decode
import traceback
import gzip

"""
加密模式：sm2非对称加密sm4密钥
"""
# 偏移量
# default_iv = '\1\2\3\4\5\6\7\x08' 失效

# 加载配置文件
cfg_path = "./config.ini"
conf = configparser.ConfigParser()
conf.read(cfg_path, encoding="utf-8")
# 学校、keys和版本信息
my_host = conf.get("Yun", "school_host") # 学校的host
default_key = conf.get("Yun", "CipherKey") # 加密密钥
my_app_edition = conf.get("Yun", "app_edition") # app版本（我手机上是3.0.0）

# 用户信息，包括设备信息
my_token = conf.get("User", 'token') # 用户token 
my_device_id = conf.get("User", "device_id") # 设备id （据说很随机，抓包搞几次试试看）
my_key = conf.get("User", "map_key") # map_key是高德地图的开发者密钥
my_device_name = conf.get("User", "device_name") # 手机名称
my_sys_edition = conf.get("User", "sys_edition") # 安卓版本（大版本）


my_point = conf.get("Run", "point") # 当前位置
min_distance = float(conf.get("Run", "min_distance")) # 2公里
allow_overflow_distance = float(conf.get("Run", "allow_overflow_distance")) # 允许偏移超出的公里数
single_mileage_min_offset = float(conf.get("Run", "single_mileage_min_offset")) # 单次配速偏移最小
single_mileage_max_offset = float(conf.get("Run", "single_mileage_max_offset")) # 单次配速偏移最大
cadence_min_offset = int(conf.get("Run", "cadence_min_offset")) # 最小步频偏移
cadence_max_offset = int(conf.get("Run", "cadence_max_offset")) # 最大步频偏移
split_count = int(conf.get("Run", "split_count")) 
exclude_points = json.loads(conf.get("Run", "exclude_points")) # 排除点
min_consume = float(conf.get("Run", "min_consume")) # 配速最小和最大
max_consume = float(conf.get("Run", "max_consume"))
strides = float(conf.get("Run", "strides"))

PUBLIC_KEY = b64decode(conf.get("Yun", "PublicKey"))
PRIVATE_KEY = b64decode(conf.get("Yun", "PrivateKey"))

def string_to_hex(input_string):
    # 将字符串转换为十六进制表示，然后去除前缀和分隔符
    hex_string = hex(int.from_bytes(input_string.encode(), 'big'))[2:].upper()
    return hex_string
def bytes_to_hex(input_string):
    # 将字符串转换为十六进制表示，然后去除前缀和分隔符
    hex_string = hex(int.from_bytes(input_string, 'big'))[2:].upper()
    return hex_string
sm2_crypt = sm2.CryptSM2(public_key=bytes_to_hex(PUBLIC_KEY[1:]), private_key=bytes_to_hex(PRIVATE_KEY), mode=1, asn1=True)
def encode_sm4(value, SM_KEY, isBytes = False):
    crypt_sm4 = CryptSM4()
    crypt_sm4.set_key(SM_KEY, SM4_ENCRYPT)
    if not isBytes:
        encrypt_value = b64encode(crypt_sm4.crypt_ecb(value.encode("utf-8")))
    else:
        encrypt_value = b64encode(crypt_sm4.crypt_ecb(value))
    return encrypt_value.decode()
def decode_sm4(value, SM_KEY):
    crypt_sm4 = CryptSM4()
    crypt_sm4.set_key(SM_KEY, SM4_DECRYPT)
    decrypt_value = crypt_sm4.crypt_ecb(b64decode(value))
    return decrypt_value
def encrypt_sm2(info):
    encode_info = sm2_crypt.encrypt(info.encode("utf-8"))
    encode_info = b64encode(encode_info).decode()  # 将二进制bytes通过base64编码
    return encode_info
def decrypt_sm2(info):
    decode_info = b64decode(info)  # 通过base64解码成二进制bytes
    decode_info = sm2_crypt.decrypt(decode_info)
    return decode_info

def update():
    conf.write(open(cfg_path, "w+", encoding="utf-8"))

def default_post(router, data, headers=None, m_host=None, isBytes=False):
    if m_host is None:
        m_host = my_host
    url = m_host + router
    if headers is None:
        headers = {
            'token': conf.get("User", "token"),
            'isApp': 'app',
            'deviceId': conf.get("User", "device_id"),
            'deviceName': conf.get("User", "device_name"),
            'version': conf.get("Yun", "app_edition"),
            'platform': 'android',
            'Content-Type': 'application/json; charset=utf-8',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'okhttp/3.12.0',
            'utc':str(int(time.time())),
            'uuid': conf.get("User", "uuid"),
            'sign': conf.get("User", "sign")
        }
    data_json = {
        "cipherKey":conf.get("Yun", "CipherKeyEncrypted"),
        "content":encode_sm4(data, b64decode(default_key),isBytes=isBytes)
    }
    req = requests.post(url=url, data=json.dumps(data_json), headers=headers) # data进行了加密
    try:
        return decode_sm4(req.text, b64decode(default_key)).decode()
    except:
        return req.text


class Yun_For_New:

    def __init__(self):
        data = json.loads(default_post("/run/getHomeRunInfo", ""))['data']['cralist'][0]
        self.raType = data['raType']
        self.raId = data['id']
        self.strides = strides
        self.schoolId = data['schoolId']
        self.raRunArea = data['raRunArea']
        self.raDislikes = data['raDislikes']
        self.raMinDislikes = data['raDislikes']
        self.raSingleMileageMin = data['raSingleMileageMin'] + single_mileage_min_offset
        self.raSingleMileageMax = data['raSingleMileageMax'] + single_mileage_max_offset
        self.raCadenceMin = data['raCadenceMin'] + cadence_min_offset
        self.raCadenceMax = data['raCadenceMax'] + cadence_max_offset
        points = data['points'].split('|') # points 是列表
        self.my_select_points = ""
        with open("./map.json") as f:
            my_s = f.read()
            tmp = json.loads(my_s)
            self.my_select_points = tmp["mypoints"]
        for my_select_point in self.my_select_points:# 手动取点
            if my_select_point in points:
                print(my_select_point + " 存在")
            else:
                print(my_select_point + " 不存在")
                raise ValueError
        print('开始标记打卡点...')
        # for exclude_point in exclude_points:
        #     try:
        #         points.remove(exclude_point)
        #         print("成功删除打卡点", exclude_point)
        #     except ValueError:
        #         print("打卡点", exclude_point, "不存在")
        #         # 删除容易跑到学校外面的打卡点
        # 采取手动选择点的方式
        self.now_dist = 0
        i = 0
        while (self.now_dist / 1000 > min_distance + allow_overflow_distance) or self.now_dist == 0:
            i += 1
            print('第' + str(i) + '次尝试...')
            self.manageList: List[Dict] = [] # 列表的每一个元素都是字典
            self.now_dist = 0
            self.now_time = 0
            self.task_list = []
            self.task_count = 0
            self.myLikes = 0
            self.generate_task(self.my_select_points)
        self.now_time = int(random.uniform(min_consume, max_consume) * 60 * (self.now_dist / 1000))
        print('打卡点标记完成！本次将打卡' + str(self.myLikes) + '个点，处理' + str(len(self.task_list)) + '个点，总计'
              + format(self.now_dist / 1000, '.2f')
              + '公里，将耗时' + str(self.now_time // 60) + '分' + str(self.now_time % 60) + '秒')
        # 这三个只是初始化，并非最终值
        self.recordStartTime = ''
        self.crsRunRecordId = 0
        self.userName = ''

    def generate_task(self, points):
        # random_points = random.sample(points, self.raDislikes) # 在打卡点随机选raDislike个点
        
        for point_index, point in enumerate(points):
            if self.now_dist / 1000 < min_distance or self.myLikes < self.raMinDislikes: # 里程不足或者点不够
                self.manageList.append({
                    'point': point,
                    'marked': 'Y',
                    'index': point_index
                })
                self.add_task(point)
                self.myLikes += 1
                #必须的任务
            else:
                self.manageList.append({
                    'point': point,
                    'marked': 'N',
                    'index': ''
                })
                # 多余的点
        # 如果跑完了表都不够
        if self.now_dist / 1000 < min_distance:
            print('公里数不足' + str(min_distance) + '公里，将自动回跑...')
            index = 0
            while self.now_dist / 1000 < min_distance:
                self.add_task(self.manageList[index]['point'])
                index = (index + 1) % self.raDislikes

    # 每10个路径点作为一组splitPoint;
    # 若最后一组不满10个且多于1个，则将最后一组中每两个点位分取10点（含终点而不含起点），作为一组splitPoint
    # 若最后一组只有1个（这种情况只会发生在len(splitPoints) > 0），则将已插入的最后一组splitPoint的最后一个点替换为最后一组的点
    def add_task(self, point): # add_ task 传一个点，开始跑
        if not self.task_list:
            origin = my_point
        else:
            origin = self.task_list[-1]['originPoint'] # 列表的-1项当起始点
        data = {
            'key': my_key,
            'origin': origin, # 起始点
            'destination': point # 传入的点
        }
        resp = requests.get("https://restapi.amap.com/v4/direction/bicycling", params=data)
        # 规划的点
        j = json.loads(resp.text)
        split_points = []
        split_point = []
        for path in j['data']['paths']:
            self.now_dist += path['distance'] # 路径长度
            path['steps'][-1]['polyline'] += ';' + point # 补上了一个起始点
            for step in path['steps']:
                polyline = step['polyline']
                points = polyline.split(';')
                for p in points:
                    i = len(split_point)
                    distForthis = self.now_dist - path['distance']*(split_count-i)/split_count
                    timeForthis = int(((min_consume + max_consume) / 2) * 60 * (self.now_dist - path['distance']*(split_count-i)) / 1000)
                    split_point.append({
                        'point': p,
                        'runStatus': '1',
                        'speed': format((min_consume + max_consume)/2, '.2f'),
                        # 最小和最大速度之间的随机
                        'isFence': 'Y',
                        'isMock': False,
                        "runMileage": distForthis,
                        "runTime": timeForthis
                    })
                    if len(split_point) == split_count:
                        # 到了10个，加入列表组中
                        split_points.append(split_point)
                        # 任务数量加一
                        self.task_count = self.task_count + 1
                        # 清空组
                        split_point = []

        if len(split_point) > 1: # 不满10个且多于一个
            b = split_point[0]['point']
            # 上一个点坐标
            for i in range(1, len(split_point)):
                # 建立一个分割列表
                new_split_point = []
                # 保存上一个点的信息
                a = b
                b = split_point[i]['point']
                # 对a和b求坐标
                a_split = a.split(',')
                b_split = b.split(',')
                a_x = float(a_split[0])
                a_y = float(a_split[1])
                b_x = float(b_split[0])
                b_y = float(b_split[1])
                # 真就均匀等分啊
                d_x = (b_x - a_x) / split_count
                d_y = (b_y - a_y) / split_count
                # 补上10个点
                for j in range(0, split_count):
                    distForthis = self.now_dist - (path['distance']/len(split_point))*(split_count-j)/split_count
                    timeForthis = int(((min_consume + max_consume) / 2) * 60 * (self.now_dist - (path['distance']/len(split_point))*(split_count-j)/split_count) / 1000)
                    new_split_point.append({
                        'point': str(a_x + (j + 1) * d_x) + ',' + str(a_y + (j + 1) * d_y),
                        'runStatus': '1',
                        'speed': format((min_consume + max_consume)/2, '.2f'),
                        # 最小和最大速度之间的随机
                        'isFence': 'Y',
                        'isMock': False,
                        "runMileage": distForthis,
                        "runTime": timeForthis
                    })
                split_points.append(new_split_point)
                # 最后一组被分成了 2 ~ 9 组
                self.task_count = self.task_count + 1
        elif len(split_point) == 1: # 直接把最后一个点扔进去
            split_points[-1][-1] = split_point[0] # 最后的最后点直接替换
        # 把任务列表加入
        self.task_list.append({
            'originPoint': point,
            'points': split_points
        })

    def start(self):
        data = {
            'raRunArea': self.raRunArea,
            'raType': self.raType,
            'raId': self.raId
        }
        j = json.loads(default_post('/run/start', json.dumps(data)))
        # 发送开始请求
        if j['code'] == 200:
            self.recordStartTime = j['data']['recordStartTime']
            self.crsRunRecordId = j['data']['id']
            self.userName = j['data']['studentId']
            print("云运动任务创建成功！")

    def split(self, points):
        data = {
            "StepNumber": int(points[9]['runMileage'] - points[0]['runMileage']) / self.strides,
            'a': 0,
            'b': None,
            'c': None,
            "mileage": points[9]['runMileage'] - points[0]['runMileage'],
            "orientationNum": 0,
            "runSteps": random.uniform(self.raCadenceMin, self.raCadenceMax),
            'cardPointList': points,
            "simulateNum": 0,
            "time": points[9]['runTime'] - points[0]['runTime'],
            'crsRunRecordId': self.crsRunRecordId,
            "speeds": format((min_consume + max_consume)/2, '.2f'),
            'schoolId': self.schoolId,
            "strides": self.strides,
            'userName': self.userName
        }
        resp = default_post("/run/splitPointCheating", gzip.compress(data=json.dumps(data).encode("utf-8")), isBytes=True) # 这里是特殊的接口，不清楚其他学校，但合工大的完全OK。
        # 发送一组点
        print('  ' + resp)

    def do(self):
        sleep_time = self.now_time / (self.task_count + 1)
        print('等待' + format(sleep_time, '.2f') + '秒...')
        time.sleep(sleep_time) # 隔一段时间
        for task_index, task in enumerate(self.task_list):
            print('开始处理第' + str(task_index + 1) + '个点...') # 打卡点组
            for split_index, split in enumerate(task['points']): # 一组splitpoints （高德点10个一组）
                self.split(split) # 发送一组splitpoint （发送的高德点）
                print('  第' + str(split_index + 1) + '次splitPoint发送成功！等待' + format(sleep_time, '.2f') + '秒...')
                time.sleep(sleep_time)
            print('第' + str(task_index + 1) + '个点处理完毕！')

    def finish(self):
        print('发送结束信号...')
        data = {
            'recordMileage': format(self.now_dist / 1000, '.2f'),
            'recodeCadence': random.randint(self.raCadenceMin, self.raCadenceMax),
            'recodePace': format(self.now_time / 60 / (self.now_dist / 1000), '.2f'),
            'deviceName': my_device_name,
            'sysEdition': my_sys_edition,
            'appEdition': my_app_edition,
            'raIsStartPoint': 'Y',
            'raIsEndPoint': 'Y',
            'raRunArea': self.raRunArea,
            'recodeDislikes': self.myLikes,
            'raId': self.raId,
            'raType': self.raType,
            'id': self.crsRunRecordId,
            'duration': self.now_time,
            'recordStartTime': self.recordStartTime,
            'manageList': self.manageList,
            'remake': '1'
        }
        resp = default_post("/run/finish", json.dumps(data))
        print(resp)

if __name__ == '__main__':

    print("确定数据无误：[Y/N]")
    print("Token: " + conf.get("User", "token"))
    print('deviceId: ' + conf.get("User", "device_id"))
    print('deviceName: ' +  conf.get("User", "device_name"))
    print('utc: ' + conf.get("User", "utc"))
    print('uuid: ' + conf.get("User", "uuid"))
    print('sign: ' + conf.get("User", "sign"))

    sure = input("确认：[Y/N]")
    if sure == 'Y':
        b = input("快速模式：[Y/N]")
        if b == 'Y':
            Yun = Yun_For_New()
            Yun.start()
            Yun.finish()
        else:
            Yun = Yun_For_New()
            Yun.start()
            Yun.do()
            Yun.finish()
    else:
        print("退出。")

