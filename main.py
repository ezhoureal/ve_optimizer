import time
import json
from typing import Dict, List
import matplotlib
import matplotlib.pyplot as plt
from deap import base, creator, tools
import numpy as np
import random
from config_ve import VisualEffect, send_config, DEFAULT_EFFECTS
from performance import PerformanceScoreDriver
from quality import test_quality, get_base_snapshot

class EffectChain:
    def __init__(self, init_sample: int):
        self.effectTable: Dict[str, VisualEffect] = {}      # id --> 视效
        self.typeIndex: Dict[str, List[str]] = {}         # 视效名字 --> id
        # self.callGraph: Dict[str, Set[str]] = {}        # id 之间的调用关系, 现阶段先不管
        self.theta = []
        send_config(DEFAULT_EFFECTS) # run baselines with default effects
        get_base_snapshot()
        self.perf_driver = PerformanceScoreDriver(init_sample_size=init_sample, verbose=True)

    def createEffect(self, eff: VisualEffect):
        name = eff.name
        if name not in self.typeIndex.keys():
            ids = name
            self.typeIndex[name] = [name]
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
                if self.effectTable[eff].update_theta(theta[3*i:3*i+3]) == 0:
                    print(f"参数 {eff} 不匹配")
                    return
                i += 1

    def initial_theta(self):
        self.theta = []
        for eff in self.effectTable.keys():
            self.theta += self.effectTable[eff].theta
    
    # def genNSamples(self, N):
    #     self.reset()
    #     for i in range(N):
    #         ex = VisualEffect("testEffect")
    #         self.createEffect(ex)
    #     # 每个视效对 q 的整体贡献
    #     self.debugQuality = np.random.randint(0, 10001, N)
    #     # 帧率对 q 的影响程度: 流畅度打分
    #     self.debugFrame = np.random.randint(0, 101, N)
    #     # 分辨率有 0.25 概率对视效影响大, 0.75 概率没什么影响
    #     self.debugResolution = np.random.uniform(0, 1, N)
    #     # 每个视效对 cost 的整体贡献
    #     self.debugCost = np.random.randint(0, 10001, N)

    def hdcLoss(self, theta):
        # 注意我们规定 loss 越小越好, loss = 0 表示满血视效
        ve_options = []
        for i, keyname in enumerate(self.effectTable.keys()):
            self.effectTable[keyname].update_theta(theta[3*i:3*i+3])
            q = self.effectTable[keyname]
            # Use theta[3*i] as the continuous o value (within value_range)
            ve_options.append(q)
        try:
            send_config(ve_options)
        except Exception as e:
            print(f"Error in VE configuration: {e}")        
        # Get quality loss via SSIM score
        try:
            quality_loss = test_quality()
        except Exception as e:
            print(f"Error in quality evaluation: {e}")
            quality_loss = float('inf')
        
        # Get performance loss via performance driver
        try:
            performance_loss = self.perf_driver.loss()
        except Exception as e:
            print(f"Error in performance evaluation: {e}")
            performance_loss = float('inf')
        print(f'evaluated performance loss: {performance_loss}, quality loss: {quality_loss}')
        return performance_loss, quality_loss

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

def effectCodeGen(chain: EffectChain) -> list[float]:
    """Generate initial effect code with continuous o values within value_range bounds.
    
    Returns:
        List of parameters: [o_0, t_0, s_0, o_1, t_1, s_1, ...]
        where o is continuous within range, t and s are discrete (0-3)
    """
    a = []
    for effect in chain.effectTable.values():
        o_min, o_max =  effect.value_range
        # Generate continuous o value within range
        a.append(np.random.uniform(o_min, o_max))
        # Discrete values for frame rate and resolution
        a.append(np.random.randint(0, 4))
        a.append(np.random.randint(0, 4))
    return a

class SimpleGASolver:
    def __init__(self, effChain: EffectChain, isEvaluate = False):
        self.effChain = effChain
        self.isEvaluate = isEvaluate
        creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0)) # -1 是最小化问题
        creator.create("Individual", list, fitness=creator.FitnessMulti)   # 创建个体类
        toolbox = base.Toolbox()
        toolbox.register("individual", tools.initIterate, creator.Individual, lambda: effectCodeGen(self.effChain))
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        toolbox.register("evaluate", self.evaluate)

        toolbox.register("mate", tools.cxTwoPoint)  # 两点交叉
        toolbox.register("mutate", self.mut0, indpb=0.05)
        toolbox.register("select", tools.selNSGA2)
        self.toolbox = toolbox
    
    def mut0(self, individual, indpb):
        """Mutate individual respecting value_range bounds for continuous parameters."""
        for i, eff in enumerate(self.effChain.effectTable.values()):
            # Mutate o (continuous, within effect.value_range)
            if random.random() < indpb:
                o_min, o_max = eff.value_range
                individual[3*i] = np.random.uniform(o_min, o_max)
            # Mutate t (discrete: 0-3 for frame rate)
            if random.random() < indpb:
                individual[3*i+1] = int(np.random.randint(0, 4))
            # Mutate s (discrete: 0-3 for resolution)
            if random.random() < indpb:
                individual[3*i+2] = int(np.random.randint(0, 4))
        return individual,

    def run(self, n=100, iterations=50, CXPB=0.7, MUTPB=0.2):
        self.evaluateTime = 0
        population = self.toolbox.population(n)
        fitnesses = self.toolbox.map(self.toolbox.evaluate, population)
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit

        # 迭代进化（比如50代）
        for gen in range(iterations):
            print(f'============= starting generation {gen+1}/{iterations} ================')
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
        self.evaluateTime += 1
        if self.isEvaluate:
            return self.effChain.hdcLoss(effectCode)
        return self.effChain.simpleCost(effectCode), self.effChain.simpleLoss(effectCode)

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
        # If backend is non-interactive (e.g., 'Agg'), save figure instead of showing
        try:
            backend = matplotlib.get_backend().lower()
        except Exception:
            backend = ''
        if backend == 'agg':
            out_file = 'pareto_front.png'
            plt.savefig(out_file)
            print(f"Non-interactive backend '{backend}' detected; figure saved to {out_file}")
        else:
            plt.show()

if __name__ == "__main__":
    # Test1. 随机创建 10 个效果，随机生成模拟数据并画图
    # a = effectChain()
    # a.genNSamples(10)
    # sol = simpleGASolver(a)

    # Test2. 接入真实的评估机制
    starting_time = time.time()
    a = EffectChain(init_sample=20)
    for effect in DEFAULT_EFFECTS:
        a.createEffect(effect)
    # 请在 hdcLoss 函数里对接脚本进行评估, loss 越小越好
    sol = SimpleGASolver(a, isEvaluate=True)

    pf, pop = sol.run(n = 20, iterations = 50, CXPB=0.7, MUTPB=0.2)

    # ============ PRINT RESULTS ==========================
    sol.plot_2D_PF(pf)
    # Highlight the print in yellow using ANSI escape codes (works in most terminals)
    print("\033[93m================ Result:\033[0m")
    elapsed = time.time() - starting_time
    hours = elapsed / 3600.0
    print(f'Running Time = {hours:.2f} hours')

    # Helper to pretty-print an individual's config
    def _print_config(individual, chain, header=None):
        if header:
            print(header)
        print(f'  Objectives (Cost, Quality Loss): {individual.fitness.values}')
        for i, eff_id in enumerate(chain.effectTable.keys()):
            o = individual[3*i]
            t = int(individual[3*i+1])
            s = int(individual[3*i+2])
            print(f'    {eff_id}: value={o:.6f}, t={t}, s={s}')
        print('')

    # Ensure we have pareto solutions
    pareto_list = list(pf)
    if len(pareto_list) == 0:
        print('No Pareto solutions found.')
    else:
        # Print all Pareto solutions summary (optional - can be removed if too verbose)
        print(f'Found {len(pareto_list)} Pareto solutions. Listing best configs:')

        # Best by cost (objective 0)
        best_cost = min(pareto_list, key=lambda ind: ind.fitness.values[0])
        _print_config(best_cost, a, header='Best (min) Cost configuration:')

        # Best by quality (objective 1)
        best_quality = min(pareto_list, key=lambda ind: ind.fitness.values[1])
        _print_config(best_quality, a, header='Best (min) Quality Loss configuration:')

        # Export all Pareto solutions to JSON
        pareto_export = []
        for ind in pareto_list:
            score = {
                "cost": float(ind.fitness.values[0]),
                "quality_loss": float(ind.fitness.values[1])
            }
            # Build config dict matching config.json format (name -> value)
            config = {}
            for i, eff_id in enumerate(a.effectTable.keys()):
                # Each individual stores triples [value, frameRate, resolution]
                config[eff_id] = float(ind[3*i])

            pareto_export.append({
                "score": score,
                "config": config
            })

        out_filename = 'pareto_solutions.json'
        with open(out_filename, 'w') as jf:
            json.dump(pareto_export, jf, indent=4)
        print(f'Pareto solutions exported to {out_filename}')

        

