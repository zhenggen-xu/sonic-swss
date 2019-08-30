from swsscommon import swsscommon
import time

class TestPortConfigChanges(object):

    admin_status_app2asic_map = {
        "down" : "false",
        "up" : "true"
    }

    default_mtu = "9100"
    default_admin_status = "down"

    def convert_mtu_app2asic(self, mtu):
        return str(int(mtu) + 22)


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


    def check_app_asic_table_mtu(self, dvs, app_tbl, asic_tbl, port, app_mtu):
        # checck app table values
        self.check_table_key_field_value(app_tbl, port, \
        "mtu", app_mtu)

        # check asic table values
        port_oid = dvs.asicdb.portnamemap[port]
        asic_mtu = self.convert_mtu_app2asic(app_mtu)
        self.check_table_key_field_value(asic_tbl, port_oid, \
        "SAI_PORT_ATTR_MTU", asic_mtu)


    def check_app_asic_table_admin_status(self, dvs, app_tbl, asic_tbl, port, admin_status):
        # checck app table values
        self.check_table_key_field_value(app_tbl, port, \
        "admin_status", admin_status)

        # check asic table values
        port_oid = dvs.asicdb.portnamemap[port]
        asic_admin_statue = self.admin_status_app2asic_map[admin_status]
        self.check_table_key_field_value(asic_tbl, port_oid, \
        "SAI_PORT_ATTR_ADMIN_STATE", asic_admin_statue)


    def check_kernel_mtu(self, dvs, port, mtu_value):
        mtu_loc = "/sys/class/net/{}/mtu".format(port)
        exit_code, mtu = dvs.runcmd(['sh', '-c', 'cat {}'.format(mtu_loc)])
        assert exit_code == 0
        assert mtu.strip() == mtu_value


    def check_kernel_admin_status(self, dvs, port, admin_status_value):
        assert admin_status_value == "up" or admin_status_value == "down"
        cmd = "ip link show {} up".format(port)
        exit_code, output = dvs.runcmd(['sh', '-c', cmd])
        assert exit_code == 0
        if admin_status_value == "up":
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
            # checck app and asic table values
            self.check_app_asic_table_mtu(dvs, app_port_tbl, \
            asic_port_tbl, port, self.default_mtu)

            # Check kernel settings
            self.check_kernel_mtu(dvs, port, self.default_mtu)

    def test_PortDefaultAdminStatus(self, dvs):
        self.setup_db(dvs)

        # get port names from configDB
        cfg_tbl = swsscommon.Table(self.cdb, "PORT")
        ports = cfg_tbl.getKeys()

        # check App-DB and ASIC-DB for PORT Table
        app_port_tbl = swsscommon.Table(self.pdb, "PORT_TABLE")
        asic_port_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")

        for port in ports:
            # checck app and asic table values
            self.check_app_asic_table_admin_status(dvs, app_port_tbl, \
            asic_port_tbl, port, self.default_admin_status)

            # Check kernel settings
            self.check_kernel_admin_status(dvs, port, self.default_admin_status)

    def test_PortConfigChanges(self, dvs):
        self.setup_db(dvs)

        # get tables in configDB, AppDB, ASIC-DB and StateDB
        cfg_tbl = swsscommon.Table(self.cdb, "PORT")
        app_port_tbl = swsscommon.Table(self.pdb, "PORT_TABLE")
        asic_port_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        state_port_tbl = swsscommon.Table(self.sdb, "PORT_TABLE")

        # test case 1, MTU changes for Ethernet0/2
        ports = ["Ethernet0", "Ethernet4"]
        mtu_value = "1500"
        fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])

        for port in ports:
            cfg_tbl.set(port, fvs)

        time.sleep(2)

        for port in ports:
            # checck app and asic table values
            self.check_app_asic_table_mtu(dvs, app_port_tbl, \
            asic_port_tbl, port, mtu_value)

            # Check kernel settings
            self.check_kernel_mtu(dvs, port, mtu_value)

        # test case 2: Check admin_status changes
        ports = ["Ethernet0", "Ethernet4"]
        admin_status = "up"
        fvs = swsscommon.FieldValuePairs([("admin_status", admin_status)])

        for port in ports:
            cfg_tbl.set(port, fvs)

        time.sleep(2)

        for port in ports:
            # checck app and asic table values
            self.check_app_asic_table_admin_status(dvs, app_port_tbl, \
            asic_port_tbl, port, admin_status)

            # Check kernel settings
            self.check_kernel_admin_status(dvs, port, admin_status)

        # test case 3: apply MTU multiple times, it should match the last one
        ports = ["Ethernet0", "Ethernet4"]
        for port in ports:
            mtu_value = "1500"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1600"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1700"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

        time.sleep(2)

        for port in ports:
            # checck app and asic table values
            self.check_app_asic_table_mtu(dvs, app_port_tbl, \
            asic_port_tbl, port, mtu_value)

            # Check kernel settings
            self.check_kernel_mtu(dvs, port, mtu_value)

        # test case 4:
        # Clear stateDB, change MTU multiple times, kernel should not be updated
        # Set stateDB, kernel is updated with the last one
        ports = ["Ethernet8", "Ethernet12"]

        globle_mtu_value = ""
        for port in ports:
            # clear StateDB
            state_port_tbl._del(port)

            mtu_value = "1500"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1600"
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

            mtu_value = "1700"
            globle_mtu_value = mtu_value
            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value)])
            cfg_tbl.set(port, fvs)

        time.sleep(2)

        for port in ports:
            # checck app and asic table values
            self.check_app_asic_table_mtu(dvs, app_port_tbl, \
            asic_port_tbl, port, mtu_value)

            # Check kernel settings, still default
            self.check_kernel_mtu(dvs, port, self.default_mtu)

        fvs = swsscommon.FieldValuePairs([("state", "ok")])
        for port in ports:
            # Set StateDB
            state_port_tbl.set(port, fvs)

        time.sleep(2)

        for port in ports:
            # Check kernel settings
            self.check_kernel_mtu(dvs, port, globle_mtu_value)

        # test case 5:
        # Clear StateDB, apply MTU, then admin_status. kernel should not be updated
        # Set StateDB, both kernel settings should be applied.
        ports = ["Ethernet16", "Ethernet20"]
        mtu_value = "1500"
        i = 0
        for i, port in enumerate(ports):
            # clear StateDB
            state_port_tbl._del(port)

            # admin_status changing for ports
            if i%2 == 0:
                admin_status = "up"
            else:
                admin_status = "down"

            fvs = swsscommon.FieldValuePairs([("mtu", mtu_value), \
            ("admin_status", admin_status)])
            cfg_tbl.set(port, fvs)
            time.sleep(2)

            # checck app and asic table mtu values
            self.check_app_asic_table_mtu(dvs, app_port_tbl, \
            asic_port_tbl, port, mtu_value)

            # checck app and asic table admin_status values
            self.check_app_asic_table_admin_status(dvs, app_port_tbl, \
            asic_port_tbl, port, admin_status)

            # checck app table values
            self.check_table_key_field_value(app_port_tbl, port, \
            "mtu", mtu_value)

            # Check kernel settings, still default
            self.check_kernel_mtu(dvs, port, self.default_mtu)
            self.check_kernel_admin_status(dvs, port, self.default_admin_status)

        fvs = swsscommon.FieldValuePairs([("state", "ok")])
        for port in ports:
            # Set StateDB
            state_port_tbl.set(port, fvs)

        time.sleep(2)

        for i, port in enumerate(ports):
            # kernel settings should be changed
            if i%2 == 0:
                admin_status = "up"
            else:
                admin_status = "down"

            # Check kernel settings
            self.check_kernel_mtu(dvs, port, mtu_value)
            self.check_kernel_admin_status(dvs, port, admin_status)

        # revert everything to default mtu, admin_status
        ports = cfg_tbl.getKeys()
        for port in ports:
            fvs = swsscommon.FieldValuePairs([("mtu", self.default_mtu), \
            ("admin_status", self.default_admin_status)])
            cfg_tbl.set(port, fvs)

        time.sleep(2)

        self.test_PortDefaultMTU(dvs)
        self.test_PortDefaultAdminStatus(dvs)
