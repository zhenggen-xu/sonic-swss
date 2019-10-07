from swsscommon import swsscommon
import time

default_app_mtu = "9100"
default_asic_mtu = "9122"
default_admin_status = "DOWN"

class TestPortConfigChanges(object):

    def setup_db(self, dvs):
        self.pdb = swsscommon.DBConnector(0, dvs.redis_sock, 0)
        self.adb = swsscommon.DBConnector(1, dvs.redis_sock, 0)
        self.cdb = swsscommon.DBConnector(4, dvs.redis_sock, 0)
        self.sdb = swsscommon.DBConnector(6, dvs.redis_sock, 0)

    def check_table_key_field_value(self, table, key, field, value):
        (status, fvs) = table.get(key)
        assert status == True
        for fv in fvs:
            if fv[0] == field:
                assert fv[1] == value

    def check_kernel_mtu(self, port, mtu_value):
        mtu_loc = "/sys/class/net/{}/mtu".format(port)
        exit_code, mtu = dvs.runcmd(['sh', '-c', 'cat {}'.format(mtu_loc)])
        assert exit_code.strip() == "0"
        assert mtu.strip() == mtu_value

    def check_kernel_admin_status(self, port, admin_status_value):
        assert admin_status_value == "up" or admin_status_value == "down"
        cmd = "ip link show {} up"
        exit_code, output = dvs.runcmd(['sh', '-c', cmd)
        assert exit_code.strip() == "0"
        if admin_status_value == up:
            assert output.strip() != ""
        else:
            assert output.strip() == ""

    def test_PortDefaultMTU(self, dvs):
        self.setup_db(dvs)

        # get port names from configDB
        cfg_tbl = swsscommon.Table(self.cdb, "PORT")
        ports = cfg_tbl.getKeys()

        # check App-DB and ASIC-DB for PORT Table
        app_port_tbl = swsscommon.Table(self.pdb, "PORT_TABLE")
        asic_port_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")

        for port in ports:
            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "mtu", default_app_mtu)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_MTU", default_asic_mtu)

            # Check kernel settings
            self.check_kernel_mtu(port, default_app_mtu)

    def test_PortDefaultAdminStatus(self, dvs):
        self.setup_db(dvs)

        # get port names from configDB
        cfg_tbl = swsscommon.Table(self.cdb, "PORT")
        ports = cfg_tbl.getKeys()

        # check App-DB and ASIC-DB for PORT Table
        app_port_tbl = swsscommon.Table(self.pdb, "PORT_TABLE")
        asic_port_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")

        for port in ports:
            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "admin_status", default_admin_status)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_ADMIN_STATE", default_admin_status)

            # Check kernel settings
            self.check_kernel_admin_status(port, default_admin_status)

    def test_PortConfigChanges(self, dvs):
        self.setup_db(dvs)

        # get tables in configDB, AppDB, ASICDB
        cfg_tbl = swsscommon.Table(self.cdb, "PORT")
        app_port_tbl = swsscommon.Table(self.pdb, "PORT_TABLE")
        asic_port_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        state_port_tbl = swsscommon.Table(self.sdb, "PORT_TABLE")

        # test case 1, MTU changes for Ethernet0/2
        ports = ["Ethernet0", "Etherent4"]
        mtu_value = "1500"
        mtu_asic_value = str(int(mtu_asic_value) + 22)
        fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])

        for port in ports:
            cfg_tbl.set(port, fvs)

            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "mtu", mtu_value)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_MTU", mtu_asic_value)

            # Check kernel settings
            self.check_kernel_mtu(port, mtu_value)

        # test case 2: Check admin_status changes
        ports = ["Ethernet0", "Etherent4"]
        admin_status = "up"
        fvs = swsscommon.FieldValuePairs([("admin_status", admin_status)])

        for port in ports:
            cfg_tbl.set(port, fvs)

            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "admin_status", admin_status)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_ADMIN_STATE", admin_status)

            # Check kernel settings
            self.check_kernel_admin_status(port, admin_status)

        # test case 3: apply MTU multiple times, it should match the last one
        ports = ["Ethernet0", "Etherent4"]
        for port in ports:
            mtu_value = "1500"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1600"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1700"
            mtu_asic_value = str(int(mtu_asic_value) + 22)
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)
            time.sleep(1)

            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "mtu", mtu_value)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_MTU", mtu_asic_value)

            # Check kernel settings
            self.check_kernel_mtu(port, mtu_value)

        # test case 4:
        # Clear stateDB, change MTU multiple times, kernel should not be updated
        # Set stateDB, kernel is updated with the last one
        ports = ["Ethernet8", "Etherent12"]

        globle_mtu_value = ""
        for port in ports:
            # clear StateDB
            state_port_tbl.del(port)

            mtu_value = "1500"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1600"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1700"
            mtu_asic_value = str(int(mtu_asic_value) + 22)
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            globle_mtu_value = mtu_value
            cfg_tbl.set(port, fvs)
            time.sleep(1)

            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "mtu", mtu_value)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_MTU", mtu_asic_value)

            # Check kernel settings, still default
            self.check_kernel_mtu(port, default_app_mtu)

        fvs = swsscommon.FieldValuePairs([("state", "ok")])
        for port in ports:
            # Set StateDB
            state_port_tbl.set(port, fvs)

        time.sleep(2)

        for port in ports
            # Check kernel settings
            self.check_kernel_mtu(port, globle_mtu_value)

        # test case 5:
        # Clear StateDB, apply MTU, then admin_status. kernel should not be updated
        # Set StateDB, both kernel settings should be applied.
        ports = ["Ethernet16", "Etherent20"]
        mtu_value = "1500"
        mtu_asic_value = str(int(mtu_asic_value) + 22)
        i = 0
        for i, port in enumerate(ports):
            # clear StateDB
            state_port_tbl.del(port)

            # admin_status changing for ports
            if i%2 == 0:
                admin_status = "up"
            else:
                admin_status = "down"

            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value), "admin_status", admin_status])
            cfg_tbl.set(port, fvs)
            time.sleep(2)

            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "mtu", mtu_value)

            self.check_table_key_field_value(app_port_tbl, port, \
            "admin_status", admin_status)

            # check asic table values
            port_oid = dvs.asicdb.portnamemap[port]
            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_MTU", mtu_asic_value)

            self.check_table_key_field_value(asic_port_tbl, port_oid, \
            "SAI_PORT_ATTR_ADMIN_STATE", admin_status)

            # Check kernel settings, still default
            self.check_kernel_mtu(port, default_app_mtu)
            self.check_kernel_admin_status(port, default_admin_status)

        fvs = swsscommon.FieldValuePairs([("state", "ok")])
        for port in ports:
            # Set StateDB
            state_port_tbl.set(port, fvs)

        time.sleep(2)

        for i, port in enumerate(ports):
            # admin_status changing for ports
            if i%2 == 0:
                admin_status = "up"
            else:
                admin_status = "down"

            # Check kernel settings
            self.check_kernel_mtu(port, mtu_value)
            self.check_kernel_admin_status(port, admin_status)

