import gymnasium as gym
from gymnasium import spaces
import numpy as np
import math
from env.env_functions import process_actions, calculate_reward1
from env.workload_management import workload

# ENV CLASS
class TrafficManagementEnv(gym.Env):
    def __init__(self, CPU_capacity = 1000, queue_capacity = 100, DFAAS_capacity = 8000, forward_capacity = 100,
                average_requests = 100, amplitude_requests = 50, period=50, congestione = 0):
        super().__init__()
        
        self.action_space = spaces.Box(low=0, high=1, shape=(3,), dtype=np.float32)
        self.observation_space = spaces.Box(low = np.array([50, 0, 0, 0]), high = np.array([150, 100, 100, 1]), dtype = np.float32)

        self.max_CPU_capacity = CPU_capacity
        self.max_queue_capacity = queue_capacity
        self.max_DFAAS_capacity = DFAAS_capacity
        self.max_forward_capacity = forward_capacity
        self.forward_capacity_t = self.max_forward_capacity

        self.congestione = congestione
        
        self.average_requests = average_requests
        self.amplitude_requests = amplitude_requests
        self.period = period
        self.t = 0
        
        self.queue_workload = []
        self.input_requests = self.calculate_requests()
        
    def calculate_requests(self):
        return int(self.average_requests + self.amplitude_requests * math.sin(2 * math.pi * self.t / self.period))  
    
    def reset(self):
        self.t = 0
        self.CPU_capacity = self.max_CPU_capacity
        self.queue_capacity = self.max_queue_capacity
        self.DFAAS_capacity = self.max_DFAAS_capacity
        self.forward_capacity = self.max_forward_capacity
        self.forward_capacity_t = self.max_forward_capacity
        self.queue_shares = 0
        self.queue_workload = []

        return np.array([self.input_requests, self.queue_capacity, self.forward_capacity, self.congestione], dtype=np.float32)
    
    def step(self, action):
        #1. VISUALIZZO LO STATO ATTUALE DEL SISTEMA
        print(f"Stato del Sistema: {self.congestione}")
        print(f"Queue Capacity: {self.queue_capacity}")
        print(f"Shares in Coda: {self.queue_shares}")
        print(f"Forward Capacity: {self.forward_capacity}")
        print(f"INPUT: {self.input_requests}")

        #2. ESTRAGGO, SALVO E VISUALIZZO IL NUMERO DI RICHIESTE ELABORATE LOCALMENTE, INOLTRATE E RIFIUTATE
        self.local, self.forwarded, self.rejected = process_actions(action, self.input_requests)
        print(f"LOCAL: {self.local}")
        print(f"FORWARDED: {self.forwarded}")
        print(f"REJECTED: {self.rejected}")

        #3. CALCOLO I PESI PER IL SISTEMA DI RICOMPENSA E LA REWARD
        self.QUEUE_factor = self.queue_capacity / self.max_queue_capacity
        self.FORWARD_factor = self.forward_capacity / self.max_forward_capacity
        reward = calculate_reward1(self.local, self.forwarded, self.rejected, 
                                   self.QUEUE_factor, self.FORWARD_factor, self.congestione)
        print(f"REWARD: {reward}")
        
        #4. COSTRUISCO LE LISTE DI CPU_workload E queue_workload
        # Viene fatto il campionamento delle richieste elaborate in CPU e quelle messe in coda (Classe, shares, dfaas_mb, position)
        # Il campionamento per la classe avviene da una distrib uniforme, per gli shares e i dfaas_mb da una distrib normale
        # Costruisco le liste che descrivono quanto ho elaborato in CPU in questo step e quanto ho messo in coda
        # Viene data precedenza all'elaborazione delle requests in coda dallo step precedente
        self.CPU_workload, self.queue_workload = workload.manage_workload(self.local, self.CPU_capacity, 
                                                                    self.DFAAS_capacity, self.queue_workload, 
                                                                    self.max_CPU_capacity, self.max_DFAAS_capacity)
        
        #5. AGGIORNO LO SPAZIO DELLE OSSERVAZIONI
        # Aggiorno la capacità disponibile in base al n di requests in queue_workload
        # Verifico la condizione per il done
        self.queue_capacity, self.queue_shares, self.t, done, self.forward_capacity, self.forward_capacity_t, self.congestione = workload.update_obs_space(self.queue_workload, self.queue_capacity, self.max_queue_capacity, self.t,
                                                                                                                                                        self.forward_capacity, self.forward_capacity_t, self.period, self.congestione)   
        
        self.input_requests = self.calculate_requests()
        state = np.array([self.input_requests, self.queue_capacity, self.forward_capacity, self.congestione], dtype=np.float32)
        return state, reward, done
