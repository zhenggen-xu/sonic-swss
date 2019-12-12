from swsscommon import swsscommon
import redis
import time
import os
import pytest
from pytest import *
import json
import re
from port_dpb import Port
from port_dpb import DPB

@pytest.mark.usefixtures('dpb_setup_fixture')
class TestPortDPBSystem(object):

    def verify_only_ports_exist(self, dvs, port_names):
        all_port_names = ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"]
        for port_name in all_port_names:
            p = Port(dvs, port_name)
            if port_name in port_names:
                assert(p.exists_in_config_db() == True)
                assert(p.exists_in_app_db() == True)
                assert(p.exists_in_asic_db() == True)
            else:
                assert(p.exists_in_config_db() == False)
                assert(p.exists_in_app_db() == False)
                assert(p.exists_in_asic_db() == False)

    '''
    |-----------------------------------------------------------------------------------------------------
    |                   | 1X40G | 1X100G | 4X10G | 4X25G | 2X50G | 2x25G(2)+1x50G(2) | 1x50G(2)+2x25G(2) |
    |-----------------------------------------------------------------------------------------------------
    | 1X40G             |  NA   |        |       |       |       |                   |                   |
    |-----------------------------------------------------------------------------------------------------
    | 1X100G            |       |   NA   |       |  P    |  P    |        P          |        P          |
    |-----------------------------------------------------------------------------------------------------
    | 4X10G             |       |        |  NA   |       |       |                   |                   |
    |-----------------------------------------------------------------------------------------------------
    | 4X25G             |       |   P    |       |  NA   |  P    |        P          |        P          |
    |-----------------------------------------------------------------------------------------------------
    | 2X50G             |       |   P    |       |  P    |  NA   |        P          |        P          |
    |-----------------------------------------------------------------------------------------------------
    | 2x25G(2)+1x50G(2) |       |   P    |       |  P    |  P    |        NA         |        P          |
    |-----------------------------------------------------------------------------------------------------
    | 1x50G(2)+2x25G(2) |       |   P    |       |  P    |  P    |        P          |        NA         |
    |-----------------------------------------------------------------------------------------------------

    NA    --> Not Applicable
    P     --> Pass
    F     --> Fail
    Empty --> Not Tested
    '''

    '''
    @pytest.mark.skip()
    '''
    def test_port_breakout_one(self, dvs):
        dvs.setup_db()
        dpb = DPB()
        dvs.verify_port_breakout_mode("Ethernet0", "1x100G[40G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0"])

        ########## 2X50G to all other modes and vice-versa ##########

        dvs.change_port_breakout_mode("Ethernet0", "2x50G")
        dvs.verify_port_breakout_mode("Ethernet0", "2x50G")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2"])
        print "**** 1X100G --> 2x50G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "4x25G[10G]")
        dvs.verify_port_breakout_mode("Ethernet0", "4x25G[10G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        print "**** 2x50G --> 4X25G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "2x50G")
        dvs.verify_port_breakout_mode("Ethernet0", "2x50G")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2"])
        print "**** 4X25G --> 2x50G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2"])
        print "**** 2X50G --> 2x25G(2)+1x50G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "2x50G")
        dvs.verify_port_breakout_mode("Ethernet0", "2x50G")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2"])
        print "**** 2x25G(2)+1x50G(2) --> 2x50G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2", "Ethernet3"])
        print "**** 2X50G --> 1x50G(2)+2x25G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "2x50G")
        dvs.verify_port_breakout_mode("Ethernet0", "2x50G")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2"])
        print "**** 1x50G(2)+2x25G(2) --> 2x50G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x100G[40G]")
        dvs.verify_port_breakout_mode("Ethernet0", "1x100G[40G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0"])
        print "**** 2x50G --> 1x100G passed ****"

        ########## 4X25G to all other modes and vice-versa ##########

        dvs.change_port_breakout_mode("Ethernet0", "4x25G[10G]")
        dvs.verify_port_breakout_mode("Ethernet0", "4x25G[10G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        print "**** 1x100G --> 4X25G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2", "Ethernet3"])
        print "**** 4X25G --> 1x50G(2)+2x25G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "4x25G[10G]")
        dvs.verify_port_breakout_mode("Ethernet0", "4x25G[10G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        print "**** 1x50G(2)+2x25G(2) --> 4X25G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2"])
        print "**** 4X25G --> 2x25G(2)+1x50G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "4x25G[10G]")
        dvs.verify_port_breakout_mode("Ethernet0", "4x25G[10G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        print "**** 2x25G(2)+1x50G(2) --> 4X25G passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x100G[40G]")
        dvs.verify_port_breakout_mode("Ethernet0", "1x100G[40G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0"])
        print "**** 4x25G --> 1x100G passed ****"

        ########## 1x50G(2)+2x25G(2) to all other modes and vice-versa ##########

        dvs.change_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2", "Ethernet3"])
        print "**** 1X100G --> 1x50G(2)+2x25G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2"])
        print "**** 1x50G(2)+2x25G(2) --> 2x25G(2)+1x50G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "1x50G(2)+2x25G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet2", "Ethernet3"])
        print "**** 2x25G(2)+1x50G(2) --> 1x50G(2)+2x25G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x100G[40G]")
        dvs.verify_port_breakout_mode("Ethernet0", "1x100G[40G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0"])
        print "**** 1x50G(2)+2x25G(2) --> 1x100G passed ****"

        ########## 2x25G(2)+1x50G(2) to all other modes and vice-versa ##########

        dvs.change_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        dvs.verify_port_breakout_mode("Ethernet0", "2x25G(2)+1x50G(2)")
        self.verify_only_ports_exist(dvs, ["Ethernet0", "Ethernet1", "Ethernet2"])
        print "**** 1x100G --> 2x25G(2)+1x50G(2) passed ****"

        dvs.change_port_breakout_mode("Ethernet0", "1x100G[40G]")
        dvs.verify_port_breakout_mode("Ethernet0", "1x100G[40G]")
        self.verify_only_ports_exist(dvs, ["Ethernet0"])
        print "**** 2x25G(2)+1x50G(2) --> 1x100G passed ****"
