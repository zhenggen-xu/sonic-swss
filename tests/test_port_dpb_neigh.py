from swsscommon import swsscommon
import redis
import time
import os
import pytest
import json
import re
from port_dpb import DPB

@pytest.mark.usefixtures('dpb_setup_fixture')
class TestPortDPBNeigh(object):
    def clear_srv_config(self, dvs):
        dvs.servers[0].runcmd("ip address flush dev eth0")
        dvs.servers[1].runcmd("ip address flush dev eth0")

    """
    Test port neighbor dependency for Dynamic port breakout
    - Add neighbors on port
    - Port should be able to be deleted(breakout) without dependency on neighbor on the port
    """
    def test_set_neighbor_DPB(self, dvs, testlog):
        dvs.setup_db()
        self.clear_srv_config(dvs)

        # bring up interface
        dvs.set_interface_status("Ethernet0", "up")

        # create interface
        dvs.create_l3_intf("Ethernet0", "")

        # assign IP to interface
        dvs.add_ip_address("Ethernet0", "10.0.0.1/24")

        # add neighbor
        dvs.set_neighbor("Ethernet0", "10.0.0.2", "00:01:02:03:04:05")

        # check application database
        # check that the FDB entries were inserted into State DB for Ethernet64, Ethernet68 with Vlan6
        ok, extra = dvs.is_table_entry_exists(dvs.pdb, "NEIGH_TABLE",
                        "Ethernet0:10.0.0.2",
                        [("neigh", "00:01:02:03:04:05"),
                         ("family", "IPv4"),
                        ]
        )
        assert ok, str(extra)

        # check ASIC neighbor database
        tbl = swsscommon.Table(dvs.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEIGHBOR_ENTRY")
        neighbor_entries = tbl.getKeys()
        assert len(neighbor_entries) == 1
        route = json.loads(neighbor_entries[0])
        assert route["ip"] == "10.0.0.2"

        (status, fvs) = tbl.get(neighbor_entries[0])
        assert status == True
        fvs_dict = dict(fvs)
        assert fvs_dict["SAI_NEIGHBOR_ENTRY_ATTR_DST_MAC_ADDRESS"] == "00:01:02:03:04:05"

        # remove ip address on interface
        dvs.remove_ip_address("Ethernet0", "10.0.0.1/24")

        # remove interface
        dvs.remove_l3_intf("Ethernet0")

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "NEIGH_TABLE:Ethernet0")
        neighbor_entries = tbl.getKeys()
        assert len(neighbor_entries) == 0

        # check ASIC neighbor database
        tbl = swsscommon.Table(dvs.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEIGHBOR_ENTRY")
        neighbor_entries = tbl.getKeys()
        assert len(neighbor_entries) == 0

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

    """
    Test port neighbor dependency for Dynamic port breakout
    - neighbors discovered by ARP
    - Port should be able to be deleted(breakout) without dependency on neighbor on the port
    """
    def test_arp_neigh_DPB(self, dvs, testlog):
        dvs.setup_db()
        self.clear_srv_config(dvs)

        # create l3 interface
        dvs.create_l3_intf("Ethernet0", "")

        # set ip address
        dvs.add_ip_address("Ethernet0", "10.0.0.0/31")

        # bring up interface
        dvs.set_interface_status("Ethernet0", "up")

        # set server ip address and default route
        dvs.servers[0].runcmd("ifconfig eth0 10.0.0.1/31 up")

        # get neighbor and arp entry
        rc = dvs.servers[0].runcmd("ping -c 1 10.0.0.0")
        assert rc == 0
        time.sleep(2)

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "NEIGH_TABLE:Ethernet0")
        neighbor_entries = tbl.getKeys()
        assert len(neighbor_entries) == 1
        assert neighbor_entries[0] == "10.0.0.1"
        (status, fvs) = tbl.get(neighbor_entries[0])
        assert status == True

        # remove ip address on interface
        dvs.remove_ip_address("Ethernet0", "10.0.0.0/31")

        # remove interface
        dvs.remove_l3_intf("Ethernet0")

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

    """
    Test port neighbor dependency for Dynamic port breakout
    - Add nexthop on the interface
    - Port should be able to be deleted(breakout) without dependency on nexthop on the port
    """
    def test_nexthop_DPB(self, dvs, testlog):
        dvs.setup_db()
        self.clear_srv_config(dvs)

        # create l3 interface
        dvs.create_l3_intf("Ethernet0", "")

        # set ip address
        dvs.add_ip_address("Ethernet0", "10.0.0.0/31")

        # bring up interface
        dvs.set_interface_status("Ethernet0", "up")

        # set server ip address and default route
        dvs.servers[0].runcmd("ip address add 10.0.0.1/31 dev eth0")
        dvs.servers[0].runcmd("ip address add 2.2.2.0/24 dev eth0")
        time.sleep(2)

        # add route and next hop
        dvs.runcmd("ip route add 2.2.2.0/24 nexthop via 10.0.0.1")
        dvs.runcmd("ping -c 1 2.2.2.0 -I Ethernet0")
        time.sleep(1)

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "ROUTE_TABLE")
        route_entries = tbl.getKeys()
        assert "2.2.2.0/24" in route_entries

        # check ASIC neighbor interface database
        tbl = swsscommon.Table(dvs.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP")
        nexthop_entries = tbl.getKeys()
        for key in nexthop_entries:
            (status, fvs) = tbl.get(key)
            assert status == True
            for fv in fvs:
                if fv[0] == "SAI_NEXT_HOP_ATTR_IP" and fv[1] == "10.0.0.1":
                    nexthop_found = True
                    nexthop_oid = key

        assert nexthop_found == True

        # remove route and next hop
        dvs.runcmd("ip route delete 2.2.2.0/24 nexthop via 10.0.0.1")

        # remove ip address
        dvs.remove_ip_address("Ethernet0", "10.0.0.0/31")

        # remove interface
        dvs.remove_l3_intf("Ethernet0")

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

    """
    Test port neighbor dependency for Dynamic port breakout
    - Add route on the interface
    - nexthop on port should be deleted after interface is down
    - Port should be able to be deleted(breakout) without dependency on nexthop on the port
    """
    def test_route_DPB(self, dvs, testlog):
        dvs.setup_db()
        self.clear_srv_config(dvs)

        # create l3 interface
        dvs.create_l3_intf("Ethernet0", "")

        # set ip address
        dvs.add_ip_address("Ethernet0", "10.0.0.0/31")

        # bring up interface
        dvs.set_interface_status("Ethernet0", "up")

        # set server ip address and default route
        dvs.servers[0].runcmd("ip address add 10.0.0.1/31 dev eth0")
        dvs.servers[0].runcmd("ip address add 2.2.2.0/24 dev eth0")

        # add route entry
        dvs.runcmd("vtysh -c \"configure terminal\" -c \"ip route 2.2.2.0/24 10.0.0.1\"")
        time.sleep(1)

        dvs.runcmd("ping -c 1 2.2.2.0 -I Ethernet0")

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "ROUTE_TABLE")
        route_entries = tbl.getKeys()
        assert "2.2.2.0/24" in route_entries
        time.sleep(1)

        # check ASIC route database
        tbl = swsscommon.Table(dvs.adb, "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY")
        for key in tbl.getKeys():
            route = json.loads(key)
            if route["dest"] == "2.2.2.0/24":
                route_found = True
        assert route_found == True
        time.sleep(2)

        # remove ip address
        dvs.remove_ip_address("Ethernet0", "10.0.0.0/31")

        # remove interface
        dvs.remove_l3_intf("Ethernet0")

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

    """
    Test port neighbor dependency for Dynamic port breakout
    - Add route on vlan on the interface
    - Port should be able to be deleted(breakout) without dependency on nexthop on the port
    """
    def test_vlan_DPB(self, dvs, testlog):
        dvs.setup_db()
        self.clear_srv_config(dvs)
        dvs.runcmd("sonic-clear fdb all")

        # create vlan and vlan members
        dvs.create_vlan("6")
        dvs.create_vlan_member("6", "Ethernet0")
        time.sleep(2)

        # create vlan interface
        dvs.create_l3_intf("Vlan6", "")

        # bring vlan up and assign IP to interface
        dvs.set_interface_status("Vlan6", "up")
        dvs.add_ip_address("Vlan6", "6.6.6.1/24")

        dvs.set_interface_status("Ethernet0", "up")

        dvs.servers[0].runcmd("ifconfig eth0 6.6.6.6/24 up")
        dvs.servers[0].runcmd("ip route add default via 6.6.6.1")

        # get neighbor and arp entry
        time.sleep(2)
        dvs.runcmd("ping -c 1 6.6.6.6")

        tbl = swsscommon.Table(dvs.pdb, "NEIGH_TABLE")
        status, neighbor_entry = tbl.get("Vlan6:6.6.6.6")
        assert status == True

        # bring down port
        dvs.servers[0].runcmd("ip link set down dev eth0")
        time.sleep(2)

        # remove ip address on interface
        dvs.remove_ip_address("Vlan6", "6.6.6.1/24")

        dvs.set_interface_status("Vlan6", "down")
        # remove interface
        dvs.remove_vlan_member("6", "Ethernet0")
        dvs.remove_l3_intf("Vlan6")

        dvs.remove_vlan("6")

        # verify port router interface dependency cleared
        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)
