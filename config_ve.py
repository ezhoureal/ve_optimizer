BUNDLE_NAME = "com.example.glass"
from dataclasses import dataclass
import json
import subprocess
from typing import Dict

from pyparsing import Enum


class EffectType(Enum):
    SHADER = 0      # "shader"
    FILTER = 1      # "shaderFilter"
    BLENDER = 2     # "blender"

class RateType(Enum):
    Frame30 = 3     # "30"
    Frame60 = 2  # "60"
    Frame90 = 1   # "90"
    Frame120 = 0    # "120"

class Resolution(Enum):
    FULL = 0    # "1"
    DOWN2X = 1      # "0.5"
    DOWN4X = 2      # "0.25"
    DOWN8X = 3      # "0.125"
    
@dataclass
class VisualEffect:
    name: str
    value: float = 0.0
    value_range: tuple[float, float] = (0.0, 1.0)  # (min, max) for value
    frameRate: RateType = RateType.Frame120
    resolution: Resolution = Resolution.FULL
    effectType: EffectType = EffectType.FILTER
    drawOptional: Dict[str, bool] = None

    def __str__(self):
        return f"{self.name}: type = {self.effectType}, value = {self.value}, value_range = {self.value_range}, frameRate = {self.frameRate}, resolution = {self.resolution}, option = {str(self.drawOptional)}"
    
    def update_theta(self, theta: list[float | int]):
        self.value = theta[0]
        self.frameRate = RateType(theta[1])
        self.resolution = Resolution(theta[2])

    def __post_init__(self):
        self.theta = [self.value, self.frameRate.value, self.resolution.value]

def send_config(effects: list[VisualEffect]):
    config = {}
    
    for opt in effects:
        config[opt.name] = opt.value
    
    # Generate JSON file
    FILENAME = "config.json"
    with open(FILENAME, 'w') as json_file:
        json.dump(config, json_file, indent=4)
    print(f"JSON configuration saved to {FILENAME}")
    subprocess.run("hdc shell rm /data/app/el1/bundle/public/" + BUNDLE_NAME + "/config.json", shell=True)
    subprocess.run("hdc file send " + FILENAME + " /data/app/el1/bundle/public/" + BUNDLE_NAME, shell=True)
    return config

DEFAULT_EFFECTS = [
    VisualEffect(name="blurParamsR2", value=48, value_range=(10, 100)),
    VisualEffect(name="blurParamsK", value=4, value_range=(1, 10)),
    VisualEffect(name="embossOffset", value=1.88, value_range=(0.5, 5)),
    VisualEffect(name="refractOutPx", value=20, value_range=(5, 50)),
    VisualEffect(name="downSampleFactor", value=1.0, value_range=(0.1, 1.0)),
    VisualEffect(name="envK", value=0.8, value_range=(0, 1)),
    VisualEffect(name="envB", value=0, value_range=(0, 255)),
    VisualEffect(name="envS", value=0, value_range=(0, 2)),
    VisualEffect(name="refractInPx", value=15, value_range=(5, 50)),
    VisualEffect(name="sdK", value=0.9, value_range=(0, 1)),
    VisualEffect(name="sdB", value=0, value_range=(0, 255)),
    VisualEffect(name="sdS", value=1.0, value_range=(0, 2)),
    VisualEffect(name="highLightDirectionX", value=1.0, value_range=(-1, 1)),
    VisualEffect(name="highLightDirectionY", value=-1.0, value_range=(-1, 1)),
    VisualEffect(name="highLightAngleDeg", value=45.0, value_range=(0, 360)),
    VisualEffect(name="highLightFeatherDeg", value=30.0, value_range=(0, 180)),
    VisualEffect(name="highLightWidthPx", value=2.0, value_range=(0.5, 10)),
    VisualEffect(name="highLightFeatherPx", value=1.0, value_range=(0.5, 10)),
    VisualEffect(name="highLightShiftPx", value=0.0, value_range=(-10, 10)),
    VisualEffect(name="hlK", value=0.6027, value_range=(0, 1)),
    VisualEffect(name="hlB", value=160, value_range=(0, 255)),
    VisualEffect(name="hlS", value=2.0, value_range=(0, 5)),
]

if __name__ == "__main__":
    send_config(DEFAULT_EFFECTS)