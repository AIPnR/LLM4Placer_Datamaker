
import torch
import torch.nn as nn
import numpy as np
import csv
import os,sys
import json
import pickle
from npr_reader import VPR_READER


class JSON_MAKER():
    def __init__(self, circuit_list=['stereovision3'], seed_range=200,\
                 fpga_size=112, iocap=1, arch='k6_N10_40nm', benchmark_name = 'vtr7'):
        self.circuit_list = circuit_list
        self.seed_range   = seed_range
        self.fpga_size    = fpga_size
        self.iocap        = iocap
        self.arch         = arch
        self.benchmark_name = benchmark_name

        self.file_name = benchmark_name+'_'+self.arch+'_size'+str(self.fpga_size)+'_iocap'+str(self.iocap)

        self.reward_req_info()
        self.llm_date_maker()

    
    # 保存nets_list/block_info_list/matrix用于后续reward计算
    def reward_req_info(self):
        reward_req_info = {}
        reward_req_info['nets_list'] ={}
        # for circuit in self.circuit_list:
        #     reward_req_info
            
        #     nets_list = vpr_reader.nets_list

        #     reward_req_info['nets_list'][circuit] = nets_list
        vpr_reader = VPR_READER(self.circuit_list[0], 0, self.fpga_size, self.iocap, self.arch, self.benchmark_name)
        reward_req_info['block_info_list'] = vpr_reader.block_info_list
        reward_req_info['matrix'] = vpr_reader.matrix

        reward_req_info_path = os.path.join(vpr_reader.vpr_run.vpr_out_dir, self.arch+'_size'+str(self.fpga_size)+'_iocap'+str(self.iocap)+'_info.pkl')
        with open(reward_req_info_path, 'wb') as file:
            pickle.dump(reward_req_info, file)
        

    def llm_date_maker(self):
        json_data = []
        avg_hpwl = {}; avg_wl = {}; avg_cpd = {} 
        for circuit in self.circuit_list:
            avg_hpwl[circuit] = 0; avg_wl[circuit] = 0; avg_cpd[circuit] = 0 #按电路初始化
            for seed in range(self.seed_range):
                vpr_reader = VPR_READER(circuit, seed, self.fpga_size, self.iocap, self.arch, self.benchmark_name)
                place_list      = vpr_reader.place_list
                nodes_list      = vpr_reader.nodes_list
                nets_list       = vpr_reader.nets_list
                nets_id         = vpr_reader.nets_id
                block_info_list = vpr_reader.block_info_list

                if seed==0:
                    netlist_csv_path = os.path.join(vpr_reader.vpr_run.circuit_pack_dir, circuit+'_netlist.csv')
                    netlist = self.llm_netlist_maker(netlist_csv_path, nodes_list, nets_id)

                pl_csv_path = os.path.join(vpr_reader.vpr_run.circuit_seed_dir, circuit+'_seed'+str(seed)+'_pl.csv')
                pl_file = self.llm_pl_maker(pl_csv_path, place_list)

                hpwl = self.hpwl_calculator(nets_list, place_list, block_info_list, nodes_list)
                avg_hpwl[circuit]+=hpwl; avg_wl[circuit]+=vpr_reader.wl; avg_cpd[circuit]+=vpr_reader.critical_path;#按电路初始化相加
                entry = {
                    "circuit":    circuit,
                    "seed":       seed,
                    "arch":       self.arch,
                    "fpga_size":  self.fpga_size,
                    "iocap":      self.iocap,
                    "netlist":    netlist,
                    "hpwl":       hpwl,  
                    "pl":         pl_file,
                    "wl":         vpr_reader.wl,
                    "cpd":        vpr_reader.critical_path,

                }
                json_data.append(entry)
            avg_hpwl[circuit]/=self.seed_range; avg_wl[circuit]/=self.seed_range; avg_cpd[circuit]/=self.seed_range #按电路求平均
        # 在json_data中加入avg_hpwl
        for entry in json_data:
            entry["avg_hpwl"] = avg_hpwl[entry["circuit"]]
            entry["avg_wl"]   = avg_wl  [entry["circuit"]]
            entry["avg_cpd"]  = avg_cpd [entry["circuit"]]
        
        json_path = os.path.join(vpr_reader.vpr_run.vpr_out_dir, self.file_name+'.json')
        json_data = json.dumps(json_data)
        with open(json_path, 'w') as f:
            f.write(json_data)


    def llm_pl_maker(self, pl_csv_path, place_list):
        place_list = list(place_list.values())
        place_list = [[block[0], block[2][0], block[2][1], block[3]] for block in place_list]
        
        with open(pl_csv_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['block_id', 'x', 'y', 'subblk'])
            writer.writerows(place_list)

        with open(pl_csv_path, 'r') as file:
            pl_file = file.read()
        return pl_file


    def llm_netlist_maker(self, netlist_csv_path, node_list, nets_id):
        node_list = list(node_list.values())
        llm_date_in = []
        for node_info in node_list:
            in_net_id = []
            for in_net_name in node_info[3]:
                in_net_id.append(nets_id[in_net_name])
            out_net_id = []
            for out_net_name in node_info[4]:
                out_net_id.append(nets_id[out_net_name])
            llm_date_in.append([node_info[0],node_info[2],in_net_id,out_net_id])
        
        with open(netlist_csv_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['block_id', 'block_type', 'in_net_id', 'out_net_id'])
            writer.writerows(llm_date_in)

        with open(netlist_csv_path, 'r') as file:
            netlist = file.read()
        return netlist

       
 

    def hpwl_calculator(self, nets_list, place_list, block_info_list, node_list):
        hpwl = 0
        for i, (net_name, nodes_id) in enumerate(nets_list.items()): #遍历每一个net
            net_x_list = []
            net_y_list = []
            for node_id in nodes_id:
                net_x_list.append(place_list[node_id][2][0])
                net_y = place_list[node_id][2][1]
                # net_y_list.append(self.place_list[node_id][2][1])
                height = block_info_list[node_list[node_id][2]]['height']
                for net_y_offset in range(height):
                    net_y_list.append(net_y+net_y_offset)
            #net中每一个block的横纵坐标分别存于net_row and net_y_list
            bb_x = max(net_x_list) - min(net_x_list) #一个block算一个单位距离
            bb_y = max(net_y_list) - min(net_y_list)
            hpwl += (bb_x+bb_y)
        return hpwl
    


 

if __name__ == "__main__":

    BENCHMARK_NAME = '6'
    ARCH = 'k6_frac_N10_mem32K_40nm'
    FPGA_SIZE = 56
    IOCAP=1

    circuit_list = os.listdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '../arch_blif_source/'+BENCHMARK_NAME+'_'+ARCH)))
    circuit_list = [circuit[:-5] for circuit in circuit_list]

    # 删除不能布局的电路
    circuit_not_exists = []
    for circuit in circuit_list:
        place_path = os.path.join(os.path.dirname(__file__), '../'\
                                  'vprout_'+BENCHMARK_NAME+'_'+ARCH+'_size'+str(FPGA_SIZE)+'_iocap'+str(IOCAP),\
                                  circuit, circuit+'_seed0', circuit+'.place')
        if not os.path.exists(place_path):
            circuit_not_exists.append(circuit)
    circuit_list = list(set( circuit_list) - set(circuit_not_exists))
    

    json_maker = JSON_MAKER(circuit_list=circuit_list, seed_range=20,\
                 fpga_size=FPGA_SIZE, iocap=IOCAP, arch=ARCH, benchmark_name=BENCHMARK_NAME)


    
    

