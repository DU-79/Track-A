#pragma once

#include "ModuleDef.h"
#include <string>
#include <vector>
#include <list>
#include <memory>

class Compiler final {
public:
    Compiler();
    ~Compiler();
    bool parseFilelist(const std::string& path);
    void dumpStats() const;
    const std::list<ModuleDef>& modules() const { return mods; }
    const ModuleDef* find(const std::string& name) const;
private:
    std::list<ModuleDef> mods;
    std::vector<std::string> files;
    struct Impl;
    std::unique_ptr<Impl> impl;
    std::string preproc(const std::string& src, const std::string& dir);
};
