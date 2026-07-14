#pragma once

#include "ModuleDef.h"
#include <string>
#include <list>

struct GenResult { std::string cpp; bool ok; };

GenResult generateCode(const std::list<ModuleDef>& mods, const std::string& top);
