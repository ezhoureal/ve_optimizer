BUNDLE_NAME = "com.ohos.sceneboard"

import os
import json
import subprocess
from visual import VisualEffect, VisualParams

def send_config(effects: list[VisualEffect] = None, verbose = True, dst_dir=None):
    # 此函数仅针对：单视效多参数情形, 其他情形需另外适配
    config = {}
    FILENAME = "config.json"

    if effects:
        for opt in effects[0].drawOptional:
            config[opt.name] = opt.value
        
        # Generate JSON file
        with open(FILENAME, 'w') as json_file:
            json.dump(config, json_file, indent=4)
        if dst_dir is not None:
            if not os.path.exists(dst_dir) or not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
            FILENAME_save = dst_dir + "/config.json"
            with open(FILENAME_save, 'w') as json_file:
                json.dump(config, json_file, indent=4)
        if verbose:
            print(f"JSON configuration saved to {FILENAME}")
    else: # directly push config.json
        pass
    subprocess.run("hdc shell rm /data/app/el1/bundle/public/" + BUNDLE_NAME + "/config.json")
    subprocess.run("hdc file send " + FILENAME + " /data/app/el1/bundle/public/" + BUNDLE_NAME)
    return config

DEFAULT_EFFECTS = [
    VisualEffect(name="FrostedGlass", drawOptional=[
        # Common parameters
        VisualParams(name="glassMode", value=4, value_range=(0, 5), step=1.0), # glass base blur
        
        # blurParams - 根据表格，需要将蒙层灰阶换成提亮参数
        # 表格中的值：-0.0000197*255*255, 0.0073317*255, 0.0950258，模糊半径待定
        # 这里保持原有参数结构，但值可能需要进一步确认
        VisualParams(name="blurParamsXDesktop", value=32.0, value_range=(0.0, 32.0), step=1.0),  # 小半径
        VisualParams(name="blurParamsYDesktop", value=1.0, value_range=(1.0, 20.0), step=1.0),   # 放大倍数k
        VisualParams(name="blurParamsX", value=1.0, value_range=(0.0, 1.0), step=0.1),  # 小半径
        VisualParams(name="blurParamsY", value=1.0, value_range=(1.0, 20.0), step=1.0),   # 放大倍数k
        
        # weightsEmboss - 表格中"不涉及 不传或者传默认值0,1"
        VisualParams(name="weightEmbossX", value=0.0, value_range=(0.0, 1.0), step=1.0, is_fixed=1),  # 内阴影透明度
        VisualParams(name="weightEmbossY", value=0.0, value_range=(0.0, 1.0), step=1.0, is_fixed=1),  # 环境光透明度
        
        # weightsEdl - 表格中"不涉及 不传或者传默认值0,1"
        VisualParams(name="weightsEdlX", value=1.9, value_range=(0.0, 1.0), step=0.1, is_fixed=1),    # 对角高光1透明度
        VisualParams(name="weightsEdlY", value=0.5, value_range=(0.0, 1.0), step=0.1, is_fixed=1),    # 对角高光2透明度
        
        # refractParams - 表格中"0,0"
        VisualParams(name="refractParamsX", value=0.0, value_range=(0, 1.0), step=1.0),    # refractRate
        VisualParams(name="refractParamsY", value=0.0, value_range=(0.0, 0.08), step=0.08),    # refractCoeff
        VisualParams(name="refractParamsZ", value=0.0, value_range=(0.0, 0.7), step=0.7),      # refractDistort
        
        # bgRates - 表格中"1.9,0.5"
        VisualParams(name="bgRatesX", value=0.0, value_range=(0, 1.9), step=1.9, is_fixed=1),  # cubicRate
        VisualParams(name="bgRatesY", value=0.0, value_range=(0, 0.5), step=0.5, is_fixed=1),   # quadraticRate
        
        # bgKBS - 表格中"待定"，保持原值
        VisualParams(name="bgKBS_X", value=0.8457, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),   # K
        VisualParams(name="bgKBS_Y", value=32.0/255, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),   # B
        VisualParams(name="bgKBS_Z", value=1.2, value_range=(0.8, 1.6), step=0.1, is_fixed=1),           # S
        
        # bgPos - 表格中"0，0"
        VisualParams(name="bgPosX", value=1.5, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="bgPosY", value=0.8, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="bgPosZ", value=0.5, value_range=(-0.5, 0.5), step=0.1, is_fixed=1),
        
        # bgNeg - 表格中"0.8457，32./255，1.2"
        VisualParams(name="bgNegX", value=1.8, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="bgNegY", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="bgNegZ", value=0.5, value_range=(0.8, 1.6), step=0.1, is_fixed=1),
        
        # sdParams - 表格中"1.5,0.8,0.5"
        VisualParams(name="sdParamsX", value=1.5, value_range=(-500.0, 500.0), step=0.5, is_fixed=0),     # 偏移程度
        VisualParams(name="sdParamsY", value=0.8, value_range=(0.0, 5.0), step=0.1, is_fixed=0),        # 宽度
        VisualParams(name="sdParamsZ", value=0.5, value_range=(0.0, 5.0), step=0.1, is_fixed=0),      # 羽化宽度
        
        # sdRates - 表格中"1.8,1，0.5"
        VisualParams(name="sdRatesX", value=1.8, value_range=(0.0, 1.8), step=0.1, is_fixed=1),       # cubicRate
        VisualParams(name="sdRatesY", value=1.0, value_range=(0.0, 1.0), step=0.1, is_fixed=1),       # quadraticRate
        
        # sdKBS - 表格中"不涉及"，保持原值
        VisualParams(name="sdKBS_X", value=0.9, value_range=(-20.0, 20.0), step=0.01, is_fixed=1),        # K
        VisualParams(name="sdKBS_Y", value=0.0, value_range=(-20.0, 20.0), step=0.01, is_fixed=1),        # B
        VisualParams(name="sdKBS_Z", value=1.0, value_range=(0.5, 1.5), step=0.1, is_fixed=1),          # S
        
        # sdPos - 表格中"不涉及"，保持原值
        VisualParams(name="sdPosX", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="sdPosY", value=1.7, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="sdPosZ", value=1.5, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        
        # sdNeg - 表格中"不涉及"，保持原值
        VisualParams(name="sdNegX", value=3.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="sdNegY", value=2.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="sdNegZ", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        
        # envLightParams - 表格中"不涉及"，保持原值
        VisualParams(name="envLightParamsX", value=2.0, value_range=(0.0, 500.0), step=1.0, is_fixed=1),   # 偏移程度
        VisualParams(name="envLightParamsY", value=2.0, value_range=(0.0, 20.0), step=0.1),   # 宽度
        VisualParams(name="envLightParamsZ", value=2.0, value_range=(0.0, 20.0), step=0.1),   # 羽化宽度        
        
        # envLightRates - 表格中"不涉及"，保持原值
        VisualParams(name="envLightRatesX", value=0.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),  # cubicRate
        VisualParams(name="envLightRatesY", value=0.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),  # quadraticRate
        
        # envLightKBS - 表格中"不涉及"，保持原值
        VisualParams(name="envLightKBS_X", value=0.8, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),   # K
        VisualParams(name="envLightKBS_Y", value=0.27451, value_range=(-20.0, 20.0), step=0.00001, is_fixed=1),  # B
        VisualParams(name="envLightKBS_Z", value=2.0, value_range=(0.5, 2.5), step=0.1, is_fixed=1),     # S
        
        # envLightPos - 表格中"不涉及"，保持原值
        VisualParams(name="envLightPosX", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="envLightPosY", value=1.7, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="envLightPosZ", value=1.5, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        
        # envLightNeg - 表格中"不涉及"，保持原值
        VisualParams(name="envLightNegX", value=3.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="envLightNegY", value=2.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="envLightNegZ", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        
        # edLightParams - 表格中"2,0.7"
        VisualParams(name="edLightParamsX", value=2.0, value_range=(0.0, 5.0), step=0.01, is_fixed=0),    # 宽度
        VisualParams(name="edLightParamsY", value=0.5, value_range=(0.0, 5.0), step=0.01, is_fixed=0),    # 羽化宽度
        
        # edLightAngles - 表格中"75,50"
        VisualParams(name="edLightAnglesX", value=75.0, value_range=(0.0, 180.0), step=10.0),   # angleDeg
        VisualParams(name="edLightAnglesY", value=50.0, value_range=(0.0, 180.0), step=10.0),   # featherDeg
        
        # edLightDir - 表格中"0.0076,-0.99"
        VisualParams(name="edLightDirX", value=0.0076, value_range=(-1.0, 1.0), step=0.1),       # x分量
        VisualParams(name="edLightDirY", value=-0.99, value_range=(-1.0, 1.0), step=0.1),       # y分量
        
        # edLightRates - 表格中"0,0"
        VisualParams(name="edLightRatesX", value=0.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),   # cubicRate
        VisualParams(name="edLightRatesY", value=0.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),   # quadraticRate
        
        # edLightKBS - 表格中"0.8,100./255,2.0"
        VisualParams(name="edLightKBS_X", value=0.8, value_range=(-20.0, 20.0), step=0.1, is_fixed=1), # K
        VisualParams(name="edLightKBS_Y", value=100./255, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),   # B
        VisualParams(name="edLightKBS_Z", value=2.0, value_range=(0.5, 3.0), step=0.1, is_fixed=1),      # S
        
        # edLightPos - 表格中"1,1.5,2"
        VisualParams(name="edLightPosX", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="edLightPosY", value=1.5, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="edLightPosZ", value=2.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        
        # edLightNeg - 表格中"1.7,3,1"
        VisualParams(name="edLightNegX", value=1.7, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="edLightNegY", value=3.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
        VisualParams(name="edLightNegZ", value=1.0, value_range=(-20.0, 20.0), step=0.1, is_fixed=1),
    ])
]

if __name__ == "__main__":
    send_config(DEFAULT_EFFECTS)
