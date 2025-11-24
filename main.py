from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Set
import matplotlib.pyplot as plt
from deap import base, creator, tools, algorithms
import numpy as np
import random

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
class geEffect:
    name: str
    isDraw: int = 1
    frameRate: RateType = RateType.Frame120
    resolution: Resolution = Resolution.FULL
    effectType: EffectType = EffectType.FILTER
    drawOptional: Dict[str, bool] = None

    def __str__(self):
        return f"{self.name}: type = {self.effectType}, isDraw = {self.isDraw}, frameRate = {self.frameRate}, resolution = {self.resolution}, option = {str(self.drawOptional)}"

    def update_theta(self):
        if self.isDraw == 0:
            self.theta = [0]
        else:
            if not self.drawOptional:
                self.theta = [1]
            else:
                sums = 0
                qs = 0
                for s in self.drawOptional.keys():
                    sums += (self.drawOptional[s] << qs)
                    qs += 1
                self.theta = [1+sums]
        self.theta.append(self.frameRate.value)
        self.theta.append(self.resolution.value)
    
    def sync_theta(self):
        # theta = [a, b, c]
        a = self.theta[0]
        if a == 0:
            self.isDraw = 0
        elif a == 1:
            self.isDraw = 1
        else:
            self.isDraw = 1
            sums = bin(int(a - 1))[2:]
            sums = sums[::-1]
            i = 0
            for k in self.drawOptional.keys():
                if i >= len(sums):
                    self.drawOptional[k] = 0
                else:
                    self.drawOptional[k] = (sums[i] == '1')
                i += 1
        self.frameRate = RateType(self.theta[1])
        self.resolution = Resolution(self.theta[2])

    def reset_theta(self, theta):
        oldT = self.theta
        self.theta = theta
        try:
            self.sync_theta()
            return 1
        except:
            self.theta = oldT
            self.sync_theta()
            return 0

    def __post_init__(self):
        self.update_theta()

class effectChain:
    def __init__(self):
        self.effectTable: Dict[str, geEffect] = {}      # id --> 视效
        self.typeIndex: Dict[str, List[str]] = {}         # 视效名字 --> id
        # self.callGraph: Dict[str, Set[str]] = {}        # id 之间的调用关系, 现阶段先不管
        self.theta = []

    def createEffect(self, eff: geEffect):
        # 先随便写个
        name = eff.name
        if name not in self.typeIndex.keys():
            ids = name+"0"
            self.typeIndex[name] = [name+"0"]
        else:
            ids = name+str(len(self.typeIndex[name]))
            self.typeIndex[name].append(ids)
        self.effectTable[ids] = eff

    def reset(self):
        self.effectTable = {}
        self.typeIndex = {}
        self.theta = []
    
    def reset_theta(self, theta):
        if len(theta) == 3 * len(self.effectTable):
            i = 0
            for eff in self.effectTable.keys():
                if self.effectTable[eff].reset_theta(theta[3*i:3*i+3]) == 0:
                    print(f"参数 {eff} 不匹配")
                    return
                i += 1

    def initial_theta(self):
        self.theta = []
        for eff in self.effectTable.keys():
            self.theta += self.effectTable[eff].theta
    
    def genNSamples(self, N):
        self.reset()
        for i in range(N):
            ex = geEffect("testEffect")
            self.createEffect(ex)
        # 每个视效对 q 的整体贡献
        self.debugQuality = np.random.randint(0, 10001, N)
        # 帧率对 q 的影响程度: 流畅度打分
        self.debugFrame = np.random.randint(0, 101, N)
        # 分辨率有 0.25 概率对视效影响大, 0.75 概率没什么影响
        self.debugResolution = np.random.uniform(0, 1, N)
        # 每个视效对 cost 的整体贡献
        self.debugCost = np.random.randint(0, 10001, N)

    def hdcLoss(self, theta):
        # 注意我们规定 loss 越小越好, loss = 0 表示满血视效
        infodict = {}
        for i, keyname in enumerate(self.effectTable.keys()):
            self.effectTable[keyname].reset_theta(theta[3*i:3*i+3])
            q = self.effectTable[keyname]
            infodict[keyname] = {"isDraw": q.isDraw, "frameRate": q.frameRate, "resolution": q.resolution, "option": str(q.drawOptional)}
        # 实际应注释下一行, 将 infodict 传给执行脚本获取 cost, 并返回对应的 loss
        return infodict

    def simpleLoss(self, theta):
        loss = 0
        for i in range(len(self.effectTable.keys())):
            lossAll = self.debugQuality[i]
            a = theta[3*i]
            if a == 0:
                loss += lossAll
                continue
            p = theta[3*i+1]
            if p > 0:
                lossAll *= 0.25 * p * self.debugFrame[i] / 300
            r = theta[3*i+2]
            if self.debugResolution[i] > 0.75:
                loss += 0.25 * r * lossAll
            else:
                loss += 0.25 * r * lossAll / 20
        return loss

    def simpleCost(self, theta):
        cost = 0
        for i in range(len(self.effectTable.keys())):
            costAll = self.debugCost[i]
            a = theta[3*i]
            if a == 0:
                continue
            r = theta[3*i+2]
            if r == 1:
                costAll *= 0.3
            elif r == 2:
                costAll *= 0.2
            elif r == 3:
                costAll *= 0.1
            p = theta[3*i+1]
            cost += costAll * 0.25 * (4-p)
        return cost

def effectCodeGen(N):
    a = []
    for i in range(N):
        a.append(np.random.randint(0,2))
        a.append(np.random.randint(0,4))
        a.append(np.random.randint(0,4))
    return a

class simpleGASolver:
    def __init__(self, effChain, isEvaluate = False):
        self.effChain = effChain
        self.isEvaluate = isEvaluate
        def gen_N_effCode():
            return len(self.effChain.effectTable)
        creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0)) # -1 是最小化问题
        creator.create("Individual", list, fitness=creator.FitnessMulti)   # 创建个体类
        toolbox = base.Toolbox()
        toolbox.register("individual", tools.initIterate, creator.Individual, lambda: effectCodeGen(len(self.effChain.effectTable)))
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        toolbox.register("evaluate", self.evaluate)

        toolbox.register("mate", tools.cxTwoPoint)  # 两点交叉
        toolbox.register("mutate", self.mut0, indpb=0.05)
        toolbox.register("select", tools.selNSGA2)
        self.toolbox = toolbox
    
    def mut0(self, individual, indpb):
        for i in range(len(self.effChain.effectTable.keys())):
            if random.random() < indpb:
                individual[i*3] = np.random.randint(0,2)
            if random.random() < indpb:
                individual[i*3+1] = np.random.randint(0,4)
            if random.random() < indpb:
                individual[i*3+2] = np.random.randint(0,4)
        return individual,

    def run(self, n=100, iterations=50, CXPB=0.7, MUTPB=0.2):
        self.evaluateTime = 0
        population = self.toolbox.population(n)
        fitnesses = self.toolbox.map(self.toolbox.evaluate, population)
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit

        # 迭代进化（比如50代）
        for gen in range(iterations):
            # 选择、交叉、变异生成后代
            offspring = self.toolbox.select(population, len(population))
            offspring = list(map(self.toolbox.clone, offspring))
            # 对后代进行交叉和变异
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < CXPB:  # 交叉概率
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            for mutant in offspring:
                if random.random() < MUTPB:  # 变异概率
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values
            # 评估无效的后代
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit

            # 环境选择：用后代替换原种群
            population = self.toolbox.select(population + offspring, len(population))
        
        # 获取帕累托最优解集
        pareto_front = tools.ParetoFront()
        pareto_front.update(population)
        return pareto_front, population

    def evaluate(self, effectCode):
        return self.evaluate_cost(effectCode), self.evaluate_quality(effectCode)

    def evaluate_cost(self, effectCode):
        return self.effChain.simpleCost(effectCode)

    def evaluate_quality(self, effectCode):
        self.evaluateTime += 1
        if self.isEvaluate:
            return self.effChain.hdcLoss(effectCode)
        else:
            return self.effChain.simpleLoss(effectCode)

    def plot_2D_PF(self, pareto_front, title="Pareto-Front"):
        if isinstance(pareto_front, tools.ParetoFront):
            obj_values = [ind.fitness.values for ind in pareto_front]
        else:
            obj_values = pareto_front
        
        obj_array = np.array(obj_values)
        
        # 创建图形
        plt.figure(figsize=(10, 8))
        
        # 绘制Pareto前沿
        plt.scatter(obj_array[:, 0], obj_array[:, 1], 
                    c='red', s=50, alpha=0.7, label='Pareto-front')
        
        # 标记极端解
        if len(obj_array) > 0:
            min_idx_0 = np.argmin(obj_array[:, 0])
            min_idx_1 = np.argmin(obj_array[:, 1])
            
            plt.scatter(obj_array[min_idx_0, 0], obj_array[min_idx_0, 1], 
                    c='blue', s=100, marker='*', label='best cost')
            plt.scatter(obj_array[min_idx_1, 0], obj_array[min_idx_1, 1], 
                    c='green', s=100, marker='^', label='best quality')
        
        # 设置标签和标题
        objectives_names = ['Cost', 'Quality Loss']
        
        plt.xlabel(objectives_names[0])
        plt.ylabel(objectives_names[1])
        plt.title(title)
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # 添加解的数量信息
        plt.text(0.52, 0.98, f'Number of solutions: {len(obj_array)}', 
                transform=plt.gca().transAxes, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    # Test1. 随机创建 10 个效果，随机生成模拟数据并画图
    a = effectChain()
    a.genNSamples(10)
    sol = simpleGASolver(a)

    # Test2. 接入真实的评估机制
    # a = effectChain()
    # a.genNSamples(3)
    # 请在 hdcLoss 函数里对接脚本进行评估, loss 越小越好
    # sol = simpleGASolver(a, evaluate=True)

    pf, pop = sol.run(n = 20, iterations = 50, CXPB=0.7, MUTPB=0.2)
    sol.plot_2D_PF(pf)
