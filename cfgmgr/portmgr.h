#pragma once

#include "dbconnector.h"
#include "orch.h"
#include "producerstatetable.h"

#include <map>
#include <set>
#include <string>

namespace swss {

/* Port default admin status is down */
#define DEFAULT_ADMIN_STATUS_STR    "down"
#define DEFAULT_MTU_STR             "9100"

typedef map<string, string> KernelSettingMap;
typedef map<string, KernelSettingMap> AllPortsKernelSettingMap;

class PortMgr : public Orch
{
public:
    PortMgr(DBConnector *cfgDb, DBConnector *appDb, DBConnector *stateDb, const vector<string> &tableNames);

    using Orch::doTask;
    void doKernelSettingTask();
private:
    Table m_cfgPortTable;
    Table m_cfgLagMemberTable;
    Table m_statePortTable;
    ProducerStateTable m_appPortTable;

    set<string> m_portList;
    AllPortsKernelSettingMap m_kernelSettingMap;

    void doTask(Consumer &consumer);
    void constructKernelSettings(const KernelSettingMap &kernelsettings,
        vector<FieldValueTuple> &fvs);
    void getKernelSettingsFromFVS(KernelSettingMap &kernelsettings,
        const vector<FieldValueTuple> &fvs);
    bool saveKernelSettingsMap(const string alias,
        KernelSettingMap &kernelsettings);
    void doConfigKernelSettings(string alias, KernelSettingMap settings);
    bool setPortMtu(const string &alias, const string &mtu);
    bool setPortAdminStatus(const string &alias, const bool up);
    bool isPortStateOk(const string &alias);
};

}
