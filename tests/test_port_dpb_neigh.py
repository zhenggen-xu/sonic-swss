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

    def test_set_neighbor_DPB(self, dvs, testlog):
        dvs.setup_db()

        # bring up interface
        dvs.set_interface_status("Ethernet0", "up")

        # create interface and get rif_oid
        rif_oid = dvs.create_l3_intf("Ethernet0", "")

        # assign IP to interface
        dvs.add_ip_address("Ethernet0", "10.0.0.1/24")

        # add neighbor
        dvs.set_neighbor("Ethernet0", "10.0.0.2", "00:01:02:03:04:05")

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "NEIGH_TABLE:Ethernet0")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        assert intf_entries[0] == "10.0.0.2"
        (status, fvs) = tbl.get(intf_entries[0])
        assert status == True
        assert len(fvs) == 2
        for fv in fvs:
            if fv[0] == "neigh":
                assert fv[1] == "00:01:02:03:04:05"
            elif fv[0] == "family":
                assert fv[1] == "IPv4"
            else:
                assert False

        # check ASIC neighbor database
        tbl = swsscommon.Table(dvs.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEIGHBOR_ENTRY")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        route = json.loads(intf_entries[0])
        assert route["ip"] == "10.0.0.2"
        #assert route["rif"] == rif_oid

        (status, fvs) = tbl.get(intf_entries[0])
        assert status == True
        for fv in fvs:
            if fv[0] == "SAI_NEIGHBOR_ENTRY_ATTR_DST_MAC_ADDRESS":
                assert fv[1] == "00:01:02:03:04:05"

        # remove ip address on interface
        dvs.remove_ip_address("Ethernet0", "10.0.0.1/24")

        # bring down interface
        dvs.set_interface_status("Ethernet0", "down")

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "NEIGH_TABLE:Ethernet0")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 0

        # check ASIC neighbor database
        tbl = swsscommon.Table(dvs.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEIGHBOR_ENTRY")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 0

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

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
        dvs.servers[0].runcmd("ip address add 10.0.0.1/31 dev eth0")
        dvs.servers[0].runcmd("ip route add default via 10.0.0.0")

        # get neighbor and arp entry
        dvs.servers[0].runcmd("ping -c 1 10.0.0.0")

        # check application database
        tbl = swsscommon.Table(dvs.pdb, "NEIGH_TABLE:Ethernet0")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        assert intf_entries[0] == "10.0.0.1"
        (status, fvs) = tbl.get(intf_entries[0])
        assert status == True

        # remove ip address on interface
        dvs.remove_ip_address("Ethernet0", "10.0.0.0/31")

        # bring down interface
        dvs.set_interface_status("Ethernet0", "down")

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

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

        # bring down interface
        dvs.set_interface_status("Ethernet0", "down")
        time.sleep(2)

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

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

        # bring down interface
        dvs.set_interface_status("Ethernet0", "down")
        time.sleep(2)

        # Breakout Ethernet0
        dpb = DPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        # Breakin Ethernet0
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)
