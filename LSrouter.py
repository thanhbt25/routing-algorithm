
####################################################
# LSrouter.py
# Name:
# HUID:
#####################################################

import json
import heapq
from router import Router
from packet import Packet


class LSrouter(Router):
    """Link state routing protocol implementation."""

    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)  # Initialize base class - DO NOT REMOVE
        self.heartbeat_time = heartbeat_time
        self.last_time = 0

        self.ports = {}  # endpoint -> port
        self.neighbors = {}  # endpoint -> cost
        self.link_state_db = {}  # router -> (seq, {neighbor: cost})
        self.seq_nums = {}  # router -> seq
        self.forwarding_table = {}  # dest -> port
        self.seq = 0  # sequence number of this router

    def handle_packet(self, port, packet):
        """Process incoming packet."""
        if packet.is_traceroute:
            dst = packet.dst_addr
            if dst in self.forwarding_table:
                out_port = self.forwarding_table[dst]
                self.send(out_port, packet)
        else:
            try:
                data = json.loads(packet.content)
                sender = data["router"]
                seq = data["seq"]
                neighbors = data["neighbors"]
            except (KeyError, json.JSONDecodeError):
                return  # Invalid packet format

            if sender in self.seq_nums and seq <= self.seq_nums[sender]:
                return  # Old update, discard

            self.link_state_db[sender] = (seq, neighbors)
            self.seq_nums[sender] = seq

            self._update_forwarding_table()

            # Flood the packet to all neighbors except the sender
            for neighbor, out_port in self.ports.items():
                if out_port != port:
                    fwd_pkt = Packet(Packet.ROUTING, self.addr, neighbor, content=packet.content)
                    self.send(out_port, fwd_pkt)

    def handle_new_link(self, port, endpoint, cost):
        """Handle new link."""
        self.ports[endpoint] = port
        self.neighbors[endpoint] = cost

        self.seq += 1
        self.link_state_db[self.addr] = (self.seq, self.neighbors.copy())
        self.seq_nums[self.addr] = self.seq

        self._update_forwarding_table()
        self._broadcast_link_state()

    def handle_remove_link(self, port):
        """Handle removed link."""
        neighbor = None
        for n, p in self.ports.items():
            if p == port:
                neighbor = n
                break

        if neighbor:
            del self.ports[neighbor]
            del self.neighbors[neighbor]

            self.seq += 1
            self.link_state_db[self.addr] = (self.seq, self.neighbors.copy())
            self.seq_nums[self.addr] = self.seq

            self._update_forwarding_table()
            self._broadcast_link_state()

    def handle_time(self, time_ms):
        """Handle current time."""
        if time_ms - self.last_time >= self.heartbeat_time:
            self.last_time = time_ms
            self._broadcast_link_state()

    def _broadcast_link_state(self):
        """Broadcast the current link state to all neighbors."""
        data = {
            "router": self.addr,
            "seq": self.seq,
            "neighbors": self.neighbors
        }
        msg = json.dumps(data)
        for neighbor, port in self.ports.items():
            pkt = Packet(Packet.ROUTING, self.addr, neighbor, content=msg)
            self.send(port, pkt)

    def _update_forwarding_table(self):
        """Update the forwarding table using Dijkstra's algorithm."""
        graph = {}
        for router, (_, neighbors) in self.link_state_db.items():
            graph[router] = neighbors.copy()

        dist = {self.addr: 0}
        prev = {}
        visited = set()
        heap = [(0, self.addr)]

        while heap:
            cost_u, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            for v, weight in graph.get(u, {}).items():
                alt = cost_u + weight
                if v not in dist or alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(heap, (alt, v))

        new_table = {}
        for dest in dist:
            if dest == self.addr:
                continue
            next_hop = dest
            while prev[next_hop] != self.addr:
                next_hop = prev[next_hop]
            if next_hop in self.ports:
                new_table[dest] = self.ports[next_hop]

        self.forwarding_table = new_table

    def __repr__(self):
        """String representation for debugging."""
        return f"LSrouter(addr={self.addr}, neighbors={self.neighbors})"