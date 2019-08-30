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

typedef std::map<std::string, std::string> KernelSettingMap;
typedef std::map<std::string, KernelSettingMap> AllPortsKernelSettingMap;

class PortMgr : public Orch
{
public:
    PortMgr(DBConnector *cfgDb, DBConnector *appDb, DBConnector *stateDb, const std::vector<std::string> &tableNames);

    using Orch::doTask;
    void doKernelSettingTask();
private:
    Table m_cfgPortTable;
    Table m_cfgLagMemberTable;
    Table m_statePortTable;
    ProducerStateTable m_appPortTable;

    std::set<std::string> m_portList;
    AllPortsKernelSettingMap m_kernelSettingMap;

    void doTask(Consumer &consumer);
    void constructKernelSettings(const KernelSettingMap &kernelsettings,
        std::vector<FieldValueTuple> &fvs);
    void getKernelSettingsFromFVS(KernelSettingMap &kernelsettings,
        const std::vector<FieldValueTuple> &fvs);
    bool saveKernelSettingsMap(const std::string &alias,
        KernelSettingMap &kernelsettings);
    void doConfigKernelSettings(const std::string &alias,
        KernelSettingMap &settings);
    bool setPortMtu(const std::string &alias, const std::string &mtu);
    bool setPortAdminStatus(const std::string &alias, const bool up);
    bool isPortStateOk(const std::string &alias);
};

}
