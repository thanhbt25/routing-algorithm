from router import Router
from packet import Packet
import json

class DVrouter(Router):
    def __init__(self, addr, heartbeat_time):
        Router.__init__(self, addr)
        self.heartbeat_time = heartbeat_time
        self.last_broadcast = 0

        self.INFINITY = 16

        self.forward_table = {
            self.addr: {"cost": 0, "next_hop": self.addr, "out_port": None}
        }

        self.port_to_neighbor = {}      # port -> neighbor_addr
        self.neighbor_info = {}         # neighbor_addr -> {"port", "cost"}

    def broadcast_distance_vector(self):
        for neighbor_addr in self.neighbor_info:
            dv = {}

            for dest, info in self.forward_table.items():
                cost = info["cost"]
                next_hop = info["next_hop"]

                # Poison reverse
                if dest != neighbor_addr and next_hop == neighbor_addr:
                    dv[dest] = {
                        "cost": self.INFINITY,
                        "next_hop": next_hop
                    }
                else:
                    dv[dest] = {
                        "cost": cost,
                        "next_hop": next_hop
                    }

            packet_content = json.dumps(dv)
            port = self.neighbor_info[neighbor_addr]["port"]
            packet = Packet(Packet.ROUTING, self.addr, neighbor_addr)
            packet.content = packet_content
            self.send(port, packet)

    def handle_packet(self, port, packet):
        if packet.is_traceroute:
            dest = packet.dst_addr
            if dest in self.forward_table:
                entry = self.forward_table[dest]
                if entry["cost"] < self.INFINITY and entry["out_port"] is not None:
                    self.send(entry["out_port"], packet)
        else:
            updated = False
            neighbor = packet.src_addr
            vector = json.loads(packet.content)

            for dest, entry in vector.items():
                advertised_cost = entry["cost"]

                if advertised_cost >= self.INFINITY:
                    if dest in self.forward_table and self.forward_table[dest]["next_hop"] == neighbor:
                        self.forward_table[dest] = {
                            "cost": self.INFINITY,
                            "next_hop": None,
                            "out_port": None
                        }
                        updated = True
                    continue

                link_cost = self.neighbor_info[neighbor]["cost"]
                total_cost = min(self.INFINITY, advertised_cost + link_cost)

                if dest not in self.forward_table or total_cost < self.forward_table[dest]["cost"]:
                    self.forward_table[dest] = {
                        "cost": total_cost,
                        "next_hop": neighbor,
                        "out_port": self.neighbor_info[neighbor]["port"]
                    }
                    updated = True

            if updated:
                self.broadcast_distance_vector()

    def handle_new_link(self, port, endpoint, cost):
        self.port_to_neighbor[port] = endpoint
        self.neighbor_info[endpoint] = {
            "port": port,
            "cost": cost
        }

        self.forward_table[endpoint] = {
            "cost": cost,
            "next_hop": endpoint,
            "out_port": port
        }

        self.broadcast_distance_vector()

    def handle_remove_link(self, port):
        if port not in self.port_to_neighbor:
            return

        neighbor = self.port_to_neighbor.pop(port)
        self.neighbor_info.pop(neighbor, None)

        updated = False
        for dest in list(self.forward_table):
            if self.forward_table[dest]["out_port"] == port:
                self.forward_table[dest] = {
                    "cost": self.INFINITY,
                    "next_hop": None,
                    "out_port": None
                }
                updated = True

        if updated:
            self.broadcast_distance_vector()

    def handle_time(self, time_ms):
        if time_ms - self.last_broadcast >= self.heartbeat_time:
            self.last_broadcast = time_ms
            self.broadcast_distance_vector()

    def __repr__(self):
        return f"DVrouter(addr={self.addr})"
