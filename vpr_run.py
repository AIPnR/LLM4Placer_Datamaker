#********************************************************************************
# vpr_run
# 更新为VTR9
#————————————————————————————————————————————————————————————————————————————————
# 功能描述：
#   0. 修改fpga arch file, 按照fpga_size
#   1. 运行vpr结果保存在vpr_out对应的文件夹
#   2. 在class属性中保存各个过程文件的dir  
#————————————————————————————————————————————————————————————————————————————————

import os, sys
from xml.etree import ElementTree as ET
from concurrent.futures import ProcessPoolExecutor
import subprocess, time




class VPR_RUN():
    def __init__(self, circuit_name='stereovision3', seed=0, \
                 fpga_size=56, iocap=1, arch ='k6_frac_N10_mem32K_40nm',\
                    benchmark_name = 'vtr7'):

        #初始化变量
        self.circuit_name = circuit_name
        self.benchmark_name = benchmark_name 
        self.seed = str(seed)
        self.fpga_size = str(fpga_size)
        self.iocap = str(iocap)
        self.arch = arch

        
        #初始化各文件夹地址
        self.script_dir = os.path.dirname(__file__)
        self.arch_blif_source_dir = os.path.abspath(os.path.join(self.script_dir,'../arch_blif_source'))
        self.blif_dir = os.path.join(self.arch_blif_source_dir, self.benchmark_name+'_'+self.arch, self.circuit_name+'.blif')
        self.ori_arch_dir = os.path.join(self.arch_blif_source_dir, 'arch_file', self.arch+'.xml')
        #创建vpr_out_benchmark__arch_size->circuit->seed 三级目录
        #创建vpr_out_bench_arch_size目录
        self.vpr_out_dir = os.path.abspath(os.path.join(self.script_dir, '../vprout_'+self.benchmark_name+'_'+self.arch+'_size'+self.fpga_size+'_iocap'+self.iocap))
        if not os.path.exists(self.vpr_out_dir): os.mkdir(self.vpr_out_dir)
        self.arch_dir = self.arch_modify() #如果需要修改fpga size
        #创建vpr_circuit目录
        self.circuit_dir = os.path.join(self.vpr_out_dir, self.circuit_name)
        if not os.path.exists(self.circuit_dir): os.mkdir(self.circuit_dir)  

        #创建vpr_net_run目录
        self.circuit_pack_dir = os.path.abspath(os.path.join(self.circuit_dir, self.circuit_name+'_pack'))
        if not os.path.exists(self.circuit_pack_dir): os.mkdir(self.circuit_pack_dir)  
        self.net_dir = os.path.join(self.circuit_pack_dir, self.circuit_name+'.net') 

        #创建当前circuit的seed输出目录
        self.circuit_seed_dir = os.path.abspath(os.path.join(self.circuit_dir, self.circuit_name+'_seed'+self.seed))
        if not os.path.exists(self.circuit_seed_dir): os.mkdir(self.circuit_seed_dir)

        self.place_dir = os.path.join(self.circuit_seed_dir, self.circuit_name+'.place')
        self.cons_dir = os.path.join(self.circuit_seed_dir, self.circuit_name+'.cons.xml')
        self.route_dir = os.path.join(self.circuit_seed_dir, self.circuit_name+'.route')
        self.vpr_stdout = os.path.join(self.circuit_seed_dir, 'vpr_stdout.log')
        # self.run() #在运行vpr p&r

    #********************************************************************************
    # arch_modify
    # arch_modify(fpga_size,io_cap, circuit_vpr_out_dir)
    #————————————————————————————————————————————————————————————————————————————————
    #fun功能：修改默认的100x100的同构FPGA描述文件，为特定尺寸特定io容量的arch描述文件，
    #fun输入：fpga_size = 100, io_cap=1, 当前circuit vpr输出地址
    #fun输出：保存修改后arch文件在circuit_vpr_out_dir，并返回arch地址
    def arch_modify(self):
        new_arch_dir = os.path.join(self.vpr_out_dir, self.arch+'_size'+self.fpga_size+'_iocap'+self.iocap+'.xml')
        if not os.path.exists(new_arch_dir):
            #读取fpga_arch file, 修改 FPGA high and width
            arch_root = ET.parse(self.ori_arch_dir).getroot() # 获xml文件的内容取根标签
            layout = arch_root.find("layout")
            auto_layout = layout.find('auto_layout')
            fixed_layout = ET.Element('fixed_layout', name="fixed_layout", width=self.fpga_size, height=self.fpga_size)
            for child in list(auto_layout):
                fixed_layout.append(child)
            index = list(layout).index(auto_layout)
            layout.insert(index, fixed_layout)
            layout.remove(auto_layout)

            # 修改 io_cap
            for sub_tile in arch_root.findall('.//sub_tile[@name="io"]'):
                sub_tile.set('capacity', self.iocap)
                
            #保存修改后的文件到new_arch_dir
            new_arch_root = ET.ElementTree(arch_root)  # root为修改后的root
            new_arch_root.write(new_arch_dir, encoding='utf-8')
        return new_arch_dir

    #********************************************************************************
    # vpr_run
    #————————————————————————————————————————————————————————————————————————————————
    #fun功能：运行vpr and ace
    def pack_run(self):
        if not os.path.exists(self.net_dir):
            print('My VPR_RUN log:', 'VPR Running .net:', self.circuit_name)
            vpr_run_command = 'cd '+self.circuit_pack_dir+';'\
                +'$VTR9_ROOT/vpr/vpr '+self.arch_dir+' '+self.blif_dir+\
                    ' --pack '
            os.system(vpr_run_command)
        else:
            print('My VPR_RUN log:', 'VPR .net exist:', self.circuit_name)


    def run(self):   
        if not os.path.exists(self.net_dir): 
            print(f"Error: The .net does not exist. Pls run pack_run first")
            # sys.exit(1)
        # 在circuit_vpr_out_dir下执行对circuit的VPR，存放于circuit_vpr_out_dir
        circuit_vpr_run_name = self.circuit_name+'_seed'+ self.seed    
        if not os.path.exists(self.route_dir):
            print('My VPR_RUN log:', 'VPR Running by loading .net:', self.circuit_name+'_seed'+ self.seed)
            vpr_run_command = 'cd '+self.circuit_seed_dir+';'\
                +'$VTR9_ROOT/vpr/vpr '+self.arch_dir+' '+self.blif_dir+\
                        ' --net_file '+self.net_dir+\
                        ' --place --seed '+self.seed+\
                        ' --write_vpr_constraints '+self.cons_dir+\
                        ' --route --analysis --route_chan_width 300'
            os.system(vpr_run_command)
        else:
            print('My VPR_RUN log:', 'VPR route exist:', circuit_vpr_run_name)

    #********************************************************************************
    # 把特定block_loc写为cons并保存
    #————————————————————————————————————————————————————————————————————————————————
    #fun功能：
    def constrain_write(self, block_loc, new_cons_path):
        tree = ET.parse(self.cons_dir)
        root = tree.getroot().find('partition_list') # 获xml文件的内容取根标签
        for partition in root.findall('partition'):
            block_name = partition.get('name')
            if block_name in block_loc:
                x = str(block_loc[block_name][0])
                y = str(block_loc[block_name][1])
                add_region = partition.find('add_region')
                add_region.set('x_high', x) 
                add_region.set('x_low',  x) 
                add_region.set('y_high', y) 
                add_region.set('y_low',  y) 
            else: #只保存RL放置过的block，其他block删除
                root.remove(partition)
        tree.write(new_cons_path) 


    #********************************************************************************
    # vpr_run4cons
    #————————————————————————————————————————————————————————————————————————————————
    #fun功能：运行vpr and ace
    def run4cons(self, vtr_run_epoch_dir, new_cons_path):
        # print('vtr running.......')
        vpr_run_command = 'cd '+vtr_run_epoch_dir+';'\
            +'$VTR9_ROOT/vpr/vpr '+self.arch_dir+' '+self.blif_dir+\
            ' --net_file '+ self.net_dir+ ' --read_vpr_constraints '+new_cons_path+\
            ' --place --route --analysis --route_chan_width 300'
        # os.system(vpr_run_command)
        run_command_with_status(vpr_run_command + " > /dev/null 2>&1")


def run_command_with_status(command):
    sys.stdout.write("vtr_cons running...")
    sys.stdout.flush()  # 确保立即输出
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
    while process.poll() is None:
        time.sleep(0.1)
    sys.stdout.write("\r" + " " * 20 + "\r")
    sys.stdout.flush()


if __name__ == '__main__':

    BENCHMARK_NAME = '6'
    ARCH = 'k6_frac_N10_mem32K_40nm'

    circuit_list = os.listdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '../arch_blif_source/'+BENCHMARK_NAME+'_'+ARCH)))
    circuit_list = [circuit.replace('.blif', '') for circuit in circuit_list]

    # vpr_run = VPR_RUN(circuit_name=circuit_list[0], seed=1, fpga_size=56, iocap=1, arch=ARCH, benchmark_name=BENCHMARK_NAME)
    # vpr_run.pack_run()
    # vpr_run.run() #在运行vpr p&r

    def process_vpr_vun(circuit,seed):
        vpr_run = VPR_RUN(circuit_name=circuit, seed=seed, fpga_size=56, iocap=1, arch=ARCH, benchmark_name=BENCHMARK_NAME)
        vpr_run.pack_run()
        # vpr_run.run() #在运行vpr p&r

    # 创建一个包含20个进程的进程池
    with ProcessPoolExecutor(max_workers=15) as executor:
        for circuit in circuit_list: 
            for seed in range(20):
                executor.submit(process_vpr_vun, circuit, seed)