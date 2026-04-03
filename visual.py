'''
@ Description: 
    1. 视效参数统一用 VisualParams 类表示 (包括分辨率/帧率/value/开关等), 具体含义见下
    2. VisualEffect 可以直接将所有有用参数写入 config.json, 也可以仅将非固定的参数编码成 theta 送进演化算法进行双向更新
'''

from pyparsing import Enum
from typing import Dict, List
from dataclasses import dataclass
from performance import PerformanceScoreDriver
import copy

@dataclass
class VisualParams:
    name: str
    value: float = 0.0      # 参数值
    value_range: tuple[float, float] = (0.0, 1.0)  # (min, max) for value
    step: float = 0.1       # 步长, 一般参数不需要很高的精度; -1 表示按浮点数精度处理;
    is_fixed: bool = False  # 是否固定参数值

@dataclass
class GASettings:
    COLONY_SIZE: 20
    ITERATIONS: 50
    CXPB: 0.7    # 0.7
    MUTPB: 0.2     # 0.2
    INDPB: 0.1 

def gen_onoff_param(vaule, isfixed):
    return VisualParams(name="on", value=vaule, value_range=(0, 1), step=1, is_fixed=isfixed)

def gen_frameRate_param(value, isfixed):
    return VisualParams(name="frameRate", value=value, value_range=(0, 3), step=1, is_fixed=isfixed)

def gen_resolution_param(value, isfixed):
    return VisualParams(name="resolution", value=value, value_range=(0, 3), step=1, is_fixed=isfixed)

@dataclass
class VisualEffect:
    name: str
    drawOptional: List[VisualParams] = None    # 视效参数统一以该形式传入, 这些参数需要匹配 config.json

    def __str__(self):
        sf = f"{self.name}:"
        ind = "\n" + 4 * " "
        for param in self.drawOptional:
            sf += ind + f'{param.name}: value = {param.value}'
        return sf
    
    def get_hash(self):
        s = ""
        for i in range(len(self.theta)):
            param = self.drawOptional[self.thetaInfo[i]]
            if param.step == -1:
                s += str(i) + "_" + str(hash(param.value)) + "_"
            else:
                s += str(i) + "_" + str(hash(round((param.value - param.value_range[0]) / param.step))) + "_"
        return s

    def update_theta(self, theta: list[float | int]):
        # 对于 is_fixed == 0 的参数, 可以直接用 theta 进行更新
        if len(theta) != len(self.theta):
            print("视效参数的长度错误.")
            return 0
        for i in range(len(self.theta)):
            self.drawOptional[self.thetaInfo[i]].value = theta[i]
        self.__post_init__()
        if (self.theta != theta):
            print("theta 更新有误.")
            return 0
        return 1

    def __post_init__(self):
        # is_fixed == 0 的视效参数被编码为 theta 和 thetaInfo, 用于演化算法
        self.theta = []
        self.thetaInfo = []
        for index, param in enumerate(self.drawOptional):
            if param.is_fixed != 1:
                self.theta.append(param.value)
                self.thetaInfo.append(index)

if __name__ == "__main__":
    my_effect = [
        VisualEffect(name="FrostedGlass", drawOptional=[
            VisualParams(name="glassMode", value=4, value_range=(0, 5), step=1.0),
            VisualParams(name="weightEmbossX", value=1.0, value_range=(0.0, 3.0), step=0.1),
            VisualParams(name="weightEmbossY", value=1.0, value_range=(0.0, 3.0), step=0.1),
            VisualParams(name="weightsEdlX", value=1.0, value_range=(0.0, 3.0), step=0.1),
            VisualParams(name="weightsEdlY", value=0.5, value_range=(0.0, 3.0), step=0.1, is_fixed=1),
            VisualParams(name="bgRatesX", value=-1.8792225, value_range=(-5.0, 5.0), step=0.0001),
            VisualParams(name="bgRatesY", value=2.7626955, value_range=(-5.0, 5.0), step=0.0001),
            VisualParams(name="bgKBS_X", value=0.0073494, value_range=(0.0, 1.0), step=0.0001, is_fixed=1),
            VisualParams(name="bgKBS_Y", value=0.0998859, value_range=(0.0, 1.0), step=0.0001, is_fixed=1),
            VisualParams(name="bgKBS_Z", value=1.2, value_range=(0.0, 3.0), step=0.01)
        ])
    ]
    a = my_effect[0]
    print(a.get_hash())
    print(a.theta, a.thetaInfo)
    a.update_theta([1 for i in range(7)])
    print(a.get_hash())
    a.update_theta([1,2,3,0])
    print(a.get_hash())
    a.update_theta([1 for i in range(4)])
    print(a.get_hash())
