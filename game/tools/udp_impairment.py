"""Per-client UDP proxy with deterministic loss and round-trip delay."""
import heapq
import random
import select
import socket
import threading
import time

class ImpairedLink:
    def __init__(self, destination, latency_ms=0, loss=0, seed=0):
        self.front = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.front.bind(('127.0.0.1',0))
        self.back = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.back.connect(destination)
        self.port = self.front.getsockname()[1]
        self.delay = latency_ms/2000.0
        self.loss = loss
        self.random = random.Random(seed)
        self.stopping = threading.Event()
        self.count = 0
        self.dropped = 0
        self.bytes = 0
        self.thread = threading.Thread(target=self.run,daemon=True)
        self.thread.start()

    def run(self):
        queue=[]
        address=None
        while not self.stopping.is_set():
            ready,_,_=select.select([self.front,self.back],[],[],.005)
            for connection in ready:
                try:
                    packet,origin=connection.recvfrom(65535)
                except ConnectionResetError:
                    # Windows reports ICMP from a retired game as a UDP reset.
                    # Keep the proxy alive; the client owns its silence timeout.
                    continue
                if connection is self.front: address=origin
                self.count+=1
                self.bytes+=len(packet)
                if self.random.random()<self.loss: self.dropped+=1; continue
                # Sequence number breaks equal-time heap ties without comparing sockets.
                heapq.heappush(queue,(time.monotonic()+self.delay,self.count,connection,packet,address))
            while queue and queue[0][0]<=time.monotonic():
                _,_,source,packet,recipient=heapq.heappop(queue)
                if source is self.front: self.back.send(packet)
                elif recipient: self.front.sendto(packet,recipient)

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=2)
        self.front.close()
        self.back.close()
