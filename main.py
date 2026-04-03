DATA_BASE_DIR = "data"

import os
import json
import pickle
import time
import datetime
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from deap import tools
from pymoo.indicators.hv import HV

from config_ve import send_config, DEFAULT_EFFECTS
from quality import get_base_snapshots
from visual import GASettings
from evolution import EffectChain, SimpleGASolver, init_env, initial_param_test
from performance import PerformanceScoreDriver

class PostProcess:
    def __init__(self, path=None):
        self.load_data = None
        if path is not None:
            with open(path, "rb") as f:
                self.load_data = pickle.load(f)

    def plot_2D_PF(self, pareto_front, title="Pareto-Front"):
        if isinstance(pareto_front, tools.ParetoFront):
            obj_values = [ind.fitness.values for ind in pareto_front]
        else:
            obj_values = pareto_front
        
        obj_array = np.array(obj_values)
        if len(obj_array[0, :]) == 1:
            return
        
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
        objectives_names = ['Cost(1e5 Cycles)', 'Quality Loss(-dB)']
        
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
    
    def analyse_pkl(self, load_data=None):
        if load_data is None:
            load_data = self.load_data
            if load_data is None:
                raise ValueError("请输入正确的数据: {代数: pareto_front}")

        N = 1       # 最大代数
        for key in load_data.keys():
            if isinstance(key, int):
                N = max(N, key)
        
        self.plot_2D_PF(load_data[N-1])
        myHVind = HV(ref_point=np.array([100.0, 100.0]))
        score = []
        generations = []
        evaluationTime = []
        for i in range(N):
            approx_set = np.array([ind.fitness.values for ind in load_data[i]])
            if len(approx_set[0]) == 2:
                hv_value = myHVind(approx_set)
            elif len(approx_set[0]) == 1:
                hv_value = np.min(approx_set)
            score.append(-hv_value)
            generations.append(i)
            if "evaTime" in load_data.keys():
                evaluationTime.append(load_data["evaTime"][i])
            else:
                evaluationTime.append(0)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
        ax1.plot(generations, score, 'b-o', linewidth=2, markersize=4)
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Cost value')
        ax1.set_title('Cost Convergence')
        ax1.grid(True, alpha=0.3)

        ax2.plot(generations, evaluationTime, 'b-o', linewidth=2, markersize=4)
        ax2.set_xlabel('Generation')
        ax2.set_ylabel('Evaluation time')
        ax2.set_title('Time Consuming')
        ax2.grid(True, alpha=0.3)
        try:
            backend = matplotlib.get_backend().lower()
        except Exception:
            backend = ''
        if backend == 'agg':
            out_file = 'generation_convergence.png'
            plt.savefig(out_file)
            print(f"Non-interactive backend '{backend}' detected; figure saved to {out_file}")
        else:
            # plt.savefig(out_file)
            plt.show()

    def export_pareto(self, baseEffect=DEFAULT_EFFECTS, pf=None):
        a = EffectChain(baseEffect)
        if pf is None:
            if self.load_data is None:
                raise ValueError("请输入 pareto front")
            N = 1       # 最大代数
            for key in self.load_data.keys():
                if isinstance(key, int):
                    N = max(N, key)
            pf = self.load_data[N-1]
        pareto_list = list(pf)
        if len(pareto_list) == 0:
            print('No Pareto solutions found.')
            return
        # Print all Pareto solutions summary (optional - can be removed if too verbose)
        print(f'Found {len(pareto_list)} Pareto solutions.')
        runtag = str(datetime.datetime.now().strftime("%m%d%H%M%S"))
        exportDir = os.path.join(DATA_BASE_DIR, runtag)
        os.makedirs(exportDir, exist_ok=True)

        # 在这里拿到 base 图, 做一些初始化工作
        send_config(baseEffect) # run baselines with default effects
        time.sleep(1) # wait for config to take effect
        get_base_snapshots(data_dir=exportDir)
        print(f'after base snapshot')

        # base 的性能数据也要保留
        p, q = a.hdcLoss(a.theta, dst_name="base", data_dir=exportDir)
        score = {
            "cost_evaluate": float(p),
            "quality_loss_evaluate": float(q)
        }
        json_name = os.path.join(exportDir, "base", "score.json")
        with open(json_name, 'w') as json_file:
            json.dump(score, json_file, indent=4)

        # Export all Pareto solutions to JSON
        pareto_export = []
        for num, ind in enumerate(pareto_list):
            filename = "rank"+str(num)
            p, q = a.hdcLoss(ind, dst_name=filename, data_dir=exportDir)
            if len(ind.fitness.values) == 1:
                score = {
                    "quality_loss": float(ind.fitness.values[0]),
                    "cost_evaluate": float(p),
                    "quality_loss_evaluate": float(q)
                }
            else:
                score = {
                    "cost": float(ind.fitness.values[0]),
                    "quality_loss": float(ind.fitness.values[1]),
                    "cost_evaluate": float(p),
                    "quality_loss_evaluate": float(q)
                }
            a.reset_theta(ind)
            # Build config dict matching config.json format (name -> value)
            config = {}
            for eff in a.effectTable:
                # Each individual stores triples [value, frameRate, resolution]
                for param in eff.drawOptional:
                    config[param.name] = param.value

            pareto_export.append({
                "score": score,
                "config": config
            })
            json_name = os.path.join(exportDir, filename, "score.json")
            with open(json_name, 'w') as json_file:
                json.dump(score, json_file, indent=4)

        out_filename = os.path.join(exportDir, 'pareto_solutions.json')
        with open(out_filename, 'w') as jf:
            json.dump(pareto_export, jf, indent=4)
        print(f'Pareto solutions exported to {out_filename}')

if __name__ == "__main__":
    task_now = 1

    if task_now == 0:
        # 1. 测试输出是否正确: 在 data 下生成对应的文件夹
        app = PostProcess(path = "results/1212120007.pkl")
        app.analyse_pkl()
        app.export_pareto()

    if task_now == 1:
        # 2. 测试 multi 模式遗传算法
        a = init_env(DEFAULT_EFFECTS, reboot=True)
        myset = GASettings(COLONY_SIZE=40, ITERATIONS=150, CXPB=0.7, MUTPB=0.2, INDPB=0.1)
        sol = SimpleGASolver(a)
        sol.set_params(myset)
        pf, pop = sol.run()
        app2 = PostProcess()
        app2.analyse_pkl(sol.genDict)
        app2.export_pareto(pf=pf)

    if task_now == 2:
        # 3. 测试 single 模式遗传算法 (只看效果)
        a = init_env(DEFAULT_EFFECTS)
        myset = GASettings(COLONY_SIZE=2, ITERATIONS=2, CXPB=0.99, MUTPB=0.99, INDPB=0.99)
        sol = SimpleGASolver(a, mode="single")
        sol.set_params(myset)
        pf, pop = sol.run()
        app2 = PostProcess()
        app2.analyse_pkl(sol.genDict)
        app2.export_pareto(pf=pf)

    if task_now == 3:
        # 4. 测试 repair 功能是否有效
        a = init_env(DEFAULT_EFFECTS)
        a.repair_pareto_front("results/1204143044.pkl")

    if task_now == 4:
        loss = initial_param_test(DEFAULT_EFFECTS)
