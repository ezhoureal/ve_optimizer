PERFORMANCE_BASE_SAMPLE_SIZE = 0        # 15

import pickle
import copy
import os, shutil
import time
import json
import datetime
import numpy as np
import random
import subprocess
from deap import base, creator, tools
from pymoo.indicators.hv import HV

from config_ve import send_config, DEFAULT_EFFECTS
from performance import PerformanceScoreDriver
from quality import test_quality, get_base_snapshots

class EffectChain:
    def __init__(self, eff):    # eff : List[VisualEffect]
        self.effectTable = copy.deepcopy(eff)       # 直接用链表表示视效链
        self.theta = []
        self.perf_driver = PerformanceScoreDriver(init_sample_size=PERFORMANCE_BASE_SAMPLE_SIZE, verbose=True)
        self.initial_theta()
        self.mybasedate = {}
        self.evaTime = 0
    
    def reset_theta(self, theta):
        # 仅更新 is_fixed == 0 的参数
        s = 0
        myhash = ""
        for index, eff in enumerate(self.effectTable):
            l = len(eff.theta)
            if self.effectTable[index].update_theta(theta[s: s+l]) == 0:
                print(f"视效 {eff.name} 不匹配")
                return
            s += l
            myhash += self.effectTable[index].get_hash()
        return myhash

    def initial_theta(self):
        self.theta = []
        for eff in self.effectTable:
            self.theta += eff.theta

    def hdcLoss(self, theta, dst_name=None, mode="multi", data_dir="data"):
        # 我们规定 loss 越小越好
        myhash = self.reset_theta(theta)
        if myhash in self.mybasedate.keys():
            print(f'already evaluated {myhash}')
            return self.mybasedate[myhash]

        print("="*50)
        self.evaTime += 1
        try:
            dst_dir = None
            if dst_name is not None and dst_name != -1:
                dst_dir = os.path.join(data_dir, dst_name)
            send_config(self.effectTable, verbose=False, dst_dir=dst_dir)
            time.sleep(1) # wait for config to take effect
        except Exception as e:
            raise ValueError(f"Error in VE configuration: {e}")
        # Get quality loss via SSIM score
        try:
            quality_loss = test_quality(dst_name=dst_name, data_dir=data_dir)
        except Exception as e:
            quality_loss = float('inf')
            raise ValueError(f"Error in quality evaluation: {e}")
        if mode == "single":
            print(f'evaluated quality loss: {quality_loss}')
            return quality_loss, 

        # Get performance loss via performance driver
        try:
            performance_loss, csv_name = self.perf_driver.loss()
            if dst_name is None or dst_name == -1:
                print(f'remove data csv: {csv_name}')
                os.remove(csv_name)
            else:
                shutil.move(csv_name, os.path.join(data_dir, dst_name))
        except Exception as e:
            performance_loss = float('inf')
            raise ValueError(f"Error in performance evaluation: {e}")
        print(f'evaluated performance loss: {performance_loss}, quality loss: {quality_loss}')
        self.mybasedate[myhash] = (performance_loss, quality_loss)
        return performance_loss, quality_loss

    def repair_pareto_front(self, pf):
        # 从 pf 中找到可能更好的 pf
        runtag = str(datetime.datetime.now().strftime("%m%d%H%M%S"))
        if isinstance(pf, str):
            with open(pf, "rb") as f:
                load_data = pickle.load(f)
                N = 1       # 最大代数
                for key in load_data.keys():
                    if isinstance(key, int):
                        N = max(N, key)
                pf = load_data[N-1]
        pareto_list = list(pf)
        base_theta = copy.deepcopy(self.theta)
        for num, ind in enumerate(pareto_list):
            p0, q0 = self.hdcLoss(ind)
            for i, thetavalue in enumerate(ind):
                if thetavalue != base_theta[i]:
                    ind[i] = base_theta[i]
                    p, q = self.hdcLoss(ind)
                    if q < 0.98 * q0 and p < 1.02 * p0:
                        print(f"find a better solution {num} {i} {p0} {q0} -> {p} {q}")
                        p0 = p
                        q0 = q
                    else:
                        ind[i] = thetavalue
        pareto_front = tools.ParetoFront()
        pareto_front.update(pareto_list)
        mydict = dict()
        mydict[0] = pareto_front
        with open('results/'+runtag+".pkl", "wb") as f:
            pickle.dump(mydict, f)
        return pareto_front

def effectCodeGen(chain: EffectChain, fixed = True) -> list[float]:
    """
        Generate initial effect code with unfixed visual params.
    """
    a = []
    for effect in chain.effectTable:
        for index in effect.thetaInfo:
            param = effect.drawOptional[index]
            o_min, o_max =  param.value_range
            if param.step <= 0:
                # float, 参数均匀采样
                a.append(np.random.uniform(o_min, o_max))
            else:
                # int, 按照特定的 step 均匀采样
                num_steps = int((o_max - o_min) / param.step) + 1
                step_idx = np.random.randint(0, num_steps)
                a.append(o_min + step_idx * param.step)
    return a

def runcmd_block(cmd, cwd=None):
    if cwd:
        return subprocess.run(cmd, shell = True, capture_output = True, text = True, cwd = cwd)
    return subprocess.run(cmd, shell = True, capture_output = True, text = True)

def wait_for_boot_complete():
    max_time = 120  # 最多 2 分钟
    t = 0
    while t < max_time:
        result = runcmd_block(r"hdc list targets")
        if result.stdout.strip() != '[Empty]':
            print("设备重启已完成")
            time.sleep(20)
            return result.stdout.strip()
        time.sleep(10)
        t += 10
    return None

def init_env(effectList, reboot=False):
    if reboot:
        INIT_BAT = f"setup\init-uifirsttest-PLR.bat"
        runcmd_block(INIT_BAT)
        ans = wait_for_boot_complete()
    a = EffectChain(effectList)
    # 在这里拿到 base 图, 做一些初始化工作
    send_config(effectList) # run baselines with default effects
    time.sleep(1) # wait for config to take effect
    get_base_snapshots()
    print(f'after base snapshot')
    return a

def initial_param_test(effectList):
    # 无视 isfixed 指令, 测试单个视效参数对性能的影响
    myeffList = copy.deepcopy(effectList)
    for eff_node in myeffList:
        for param in eff_node.drawOptional:
            param.is_fixed = 1  # 先全部固定
    # 参数值轮换
    flag = 0
    for eff_node in myeffList:
        for param_node in eff_node.drawOptional:
            if param_node.name == "weightEmbossX":
                flag = 1
            if flag == 0:
                continue
            param_node.is_fixed = 0  # 只放开一个
            eff_node.__post_init__()
            a = init_env(myeffList, reboot=False)
            LossDict = {}
            for eff in a.effectTable:
                for ind, param_ind in enumerate(eff.thetaInfo):
                    param = eff.drawOptional[param_ind]
                    LossDict[param.name] = {}
                    o_min, o_max =  param.value_range
                    o_v = param.value
                    for ni in range(3):
                        jishu = 0
                        for d in np.linspace(o_min, o_max, 10):
                            param.value = d
                            eff.__post_init__()
                            a.initial_theta()
                            ploss, qloss = a.hdcLoss(a.theta, dst_name=param.name+"_"+str(jishu)+"_"+str(ni))
                            jishu += 1
                            if str(d) not in LossDict[param.name].keys():
                                LossDict[param.name][str(d)] = [ploss/3, qloss/3]
                            else:
                                LossDict[param.name][str(d)][0] += ploss/3
                                LossDict[param.name][str(d)][1] += qloss/3
                            print(f"{param.name} = {d}: performance {ploss}, quality {qloss}")
                    param.value = o_v
                    with open("initial_cost_"+param.name+".json", 'w') as json_file:
                        json.dump(LossDict, json_file, indent=4)
            param_node.is_fixed = 1  # 恢复固定状态
            time.sleep(60)  # 静置一分钟, 避免过热
    return True

class SimpleGASolver:
    def __init__(self, effChain: EffectChain, mode = "multi"):
        self.effChain = effChain
        self.mode = mode
        if mode == "multi":
            creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0)) # -1 是最小化问题
        elif mode == "single":
            creator.create("FitnessMulti", base.Fitness, weights=(-1.0, ))
        else:
            raise ValueError("错误的算法 mode")
        creator.create("Individual", list, fitness=creator.FitnessMulti)   # 创建个体类
        toolbox = base.Toolbox()
        toolbox.register("individual", tools.initIterate, creator.Individual, lambda: effectCodeGen(self.effChain))
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        toolbox.register("evaluate", self.evaluate)

        toolbox.register("mate", tools.cxTwoPoint)  # 两点交叉
        toolbox.register("mutate", self.mut0)
        toolbox.register("select", tools.selNSGA2)
        self.toolbox = toolbox
        self.generation_best_scores = []  # Track best score per generation

        self.COLONY_SIZE = 20     # 20
        self.ITERATIONS = 50
        self.CXPB = 0.7    # 0.7
        self.MUTPB = 0.2     # 0.2
        self.INDPB = 0.1    # 0.1

    def set_params(self, GASet):
        self.COLONY_SIZE = GASet.COLONY_SIZE     # 20
        self.ITERATIONS = GASet.ITERATIONS
        self.CXPB = GASet.CXPB    # 0.7
        self.MUTPB = GASet.MUTPB     # 0.2
        self.INDPB = GASet.INDPB    # 0.1

    def mut0(self, individual):
        indpb = self.INDPB
        """Mutate individual respecting value_range bounds for continuous parameters."""
        index = 0
        for effect in self.effChain.effectTable:
            for infodex in effect.thetaInfo:
                param = effect.drawOptional[infodex]
                if random.random() < indpb:
                    o_min, o_max =  param.value_range
                    if param.step <= 0:
                        # float, 参数均匀采样
                        individual[index] = np.random.uniform(o_min, o_max)
                    else:
                        # int, 按照特定的 step 均匀采样
                        num_steps = int((o_max - o_min) / param.step) + 1
                        step_idx = np.random.randint(0, num_steps)
                        individual[index] = o_min + step_idx * param.step
                index += 1
        return individual,

    def run(self) -> tuple[tools.ParetoFront, any]:
        runtag = str(datetime.datetime.now().strftime("%m%d%H%M%S"))
        
        self.effChain.evaTime = 0
        # Pareto 前沿
        pareto_front = tools.ParetoFront()
        if self.mode == "multi":
            myHVind = HV(ref_point=np.array([100.0, 100.0]))

        init_env(DEFAULT_EFFECTS)

        self.genDict = dict()
        self.genDict[0] = []
        print("\n" + f'============= starting generation 0/{self.ITERATIONS} ================')
        population = self.toolbox.population(self.COLONY_SIZE)
        fitnesses = self.toolbox.map(self.toolbox.evaluate, population)
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit
        pareto_front.update(population)
        approx_set = np.array([ind.fitness.values for ind in pareto_front])
        if self.mode == "multi":
            hv_value = myHVind(approx_set)
        elif self.mode == "single":
            hv_value = np.max(approx_set)
        print("pareto set = ", approx_set)
        print(f'generation 0 hv_value: {hv_value}')
        self.genDict[0] = copy.deepcopy(pareto_front)
        self.genDict["evaTime"] = [self.effChain.evaTime]

        # 迭代进化（比如50代）
        for gen in range(self.ITERATIONS):
            print("\n" + f'============= starting generation {gen+1}/{self.ITERATIONS} ================')
            # if gen % 10 == 0:
            #     init_env(DEFAULT_EFFECTS)
            # 选择、交叉、变异生成后代
            offspring = self.toolbox.select(population, len(population))
            offspring = list(map(self.toolbox.clone, offspring))
            # 对后代进行交叉和变异
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < self.CXPB:  # 交叉概率
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            for mutant in offspring:
                if random.random() < self.MUTPB:  # 变异概率
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values
            # 评估无效的后代
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = self.toolbox.map(self.toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit

            # 环境选择：用后代替换原种群
            population = self.toolbox.select(population + offspring, len(population))

            # 每一次迭代清理得到非支配点集, 用于计算 D-metric, 或者超体积指标
            pareto_front.update(population)
            approx_set = np.array([ind.fitness.values for ind in pareto_front])
            if self.mode == "multi":
                hv_value = myHVind(approx_set)
            elif self.mode == "single":
                hv_value = np.min(approx_set)
            print("pareto set = ", approx_set)
            print(f'generation {gen+1} hv_value: {hv_value}')

            self.genDict[gen + 1] = copy.deepcopy(pareto_front)
            self.genDict["evaTime"].append(self.effChain.evaTime)
            with open('results/'+runtag+".pkl", "wb") as f:
                pickle.dump(self.genDict, f)

        # 获取帕累托最优解集
        # pareto_front.update(population)
        return pareto_front, population

    def evaluate(self, effectCode):
        ans = self.effChain.hdcLoss(effectCode, mode = self.mode)
        if self.effChain.evaTime % 50 == 0:
            print("静置: ", self.effChain.evaTime)
            time.sleep(60)      # 休息一下
            self.effChain.evaTime += 1
        return ans

if __name__ == "__main__":
    starting_time = time.time()
    a = EffectChain(DEFAULT_EFFECTS)
    # 在这里拿到 base 图, 做一些初始化工作
    send_config(DEFAULT_EFFECTS) # run baselines with default effects
    time.sleep(1) # wait for config to take effect
    get_base_snapshots()
    print(f'after base snapshot')

    # 请在 hdcLoss 函数里对接脚本进行评估, loss 越小越好
    sol = SimpleGASolver(a, mode="single")

    pf, pop = sol.run()

    # ============ PRINT RESULTS ==========================
    # Highlight the print in yellow using ANSI escape codes (works in most terminals)
    print("\033[93m================ Result:\033[0m")
    elapsed = time.time() - starting_time
    hours = elapsed / 3600.0
    print(f'Running Time = {hours:.2f} hours')
